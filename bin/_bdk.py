import argparse
import git
import jinja2
import json
import os
import re

import sys
import yaml

from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from git.util import join_path

try:
    from bonobo.logging import getLogger
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    getLogger = logging.getLogger

logger = getLogger('bdk')
tasks = []

GITHUB_PROTOCOL = os.environ.get('GITHUB_PROTOCOL', 'ssh')
assert GITHUB_PROTOCOL in ('ssh', 'https'), 'Unsupported github protocol.'


def merge(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            elif isinstance(a[key], list) and isinstance(b[key], list):
                a[key].extend(b[key])
            else:
                raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a


def load_configuration():
    gitconfig = git.GitConfigParser([os.path.normpath(os.path.expanduser("~/.gitconfig"))], read_only=True)
    github_username = gitconfig.get('github', 'user', fallback=None)

    if not github_username:
        logger.error('No github username set. Please run "git config --global github.user your-username".')

    with open('config.yml') as f:
        template = jinja2.Template(f.read())

    def _github(name, user=github_username):
        if user:
            if GITHUB_PROTOCOL == 'ssh':
                return json.dumps('git@github.com:{user}/{name}'.format(user=user, name=name))
            elif GITHUB_PROTOCOL == 'https':
                return json.dumps('https://github.com/{user}/{name}'.format(user=user, name=name))
        return 'null'

    source = template.render(github=_github)
    config = yaml.load(source)

    if os.path.exists('config.local.yml'):
        with open('config.local.yml') as f:
            template = jinja2.Template(f.read())
        source = template.render(github_username=github_username)
        config = merge(config, yaml.load(source))

    return config


def iter_repositories(repositories, *, filter_=None):
    for repository in repositories:
        assert len(repository) == 1
        path, remotes = list(repository.items())[0]
        branch = None
        extras = ''

        match = re.match('^([^@\[\]]*)(:?@[a-z0-9-]+)?\[(.*)\]$', path)
        if match:
            path, branch, extras = match.groups()
            branch = branch[1:] if branch else None

        if filter_ and path != filter_:
            continue

        if not os.path.exists(path):
            remote_url = remotes.get('origin', None)
            if not remote_url:
                remote_url = remotes.get('upstream', None)
            if not remote_url:
                raise RuntimeError('No origin or upstream configured for {}.'.format(path))

            logger.info('Cloning {} from {}'.format(path, remote_url))
            cmd = 'git clone ' + ' '.join((remote_url, path, ) + (('-b', branch, ) if branch else ()))
            logger.debug('cmd: '+cmd)
            os.system(cmd)

        repo = git.Repo(path)

        yield path, repo, remotes, extras


def create_or_update_repositories(repositories, sync=False):
    packages = []
    for path, repo, remotes, extras in iter_repositories(repositories):
        need_fetch = sync

        # update the remotes if the url does not match the config
        for remote in repo.remotes:
            if remote.name in remotes and remote.url != remotes[remote.name] and remotes[remote.name]:
                remote.set_url(remotes[remote.name])
                need_fetch = True
            remotes.pop(remote.name, None)

        # add missing remotes
        for remote, url in remotes.items():
            if url:
                need_fetch = True
                repo.create_remote(remote, url)

        if need_fetch:
            def task(path=path, remotes=repo.remotes, logger=logger):
                logger.info('Fetching {}...'.format(path))
                for remote in remotes:
                    remote.fetch(tags=True)
                    logger.info('  ...fetched {}:{}.'.format(path, remote.name))

            tasks.append(task)

        if os.path.exists(os.path.join(path, 'setup.py')):
            packages.append('-e {}{}'.format(path, '[' + extras + ']' if extras else ''))

    with open('.requirements.local.txt', 'w+') as f:
        f.write('\n'.join(packages))


def format_diff(diff, *, reverse=False):
    if isinstance(diff, git.diff.Diff):
        if diff.deleted_file if reverse else diff.new_file:
            return '\tnew file:   ' + diff.b_path
        elif diff.new_file if reverse else diff.deleted_file:
            return '\tdeleted:    ' + diff.b_path
        elif diff.a_path == diff.b_path:
            return '\tmodified:   ' + diff.a_path
        else:
            a, b = (diff.b_path, diff.a_path) if reverse else (diff.a_path, diff.b_path)
            return '\trenamed:    ' + a + ' -> ' + b
    return '\t' + str(diff)


def get_repositories_status(repositories, filter_=None):
    for path, repo, remotes, extras in iter_repositories(repositories, filter_=filter_):
        if repo.is_dirty(untracked_files=True):
            print_repo_header(path, repo)
            for diff, name, color, reverse in (
                    (repo.index.diff(repo.head.commit), 'Changes to be committed:', Fore.GREEN, True),
                    (repo.index.diff(None), 'Changes not staged for commit:', Fore.RED, False),
                    (repo.untracked_files, 'Untracked files:', Fore.RED, False),):
                if len(diff):
                    print()
                    print('  ', name)
                    print(color, '\n'.join(map(partial(format_diff, reverse=reverse), diff)), Fore.RESET, sep='')
            print()
        else:
            if print_repo_header(path, repo, only_if_counts=True):
                print()


def format_count(cnt, sfg, efg):
    return ' {}(+{}){}'.format(sfg, cnt, efg) if cnt else ''


def print_repo_header(path, repo, only_if_counts=False):
    active_branch = repo.active_branch
    tracking_branch = repo.active_branch.tracking_branch()
    local_count = len(list(repo.iter_commits('{}..{}'.format(tracking_branch, active_branch))))
    remote_count = len(list(repo.iter_commits('{}..{}'.format(active_branch, tracking_branch))))

    if not only_if_counts or local_count or remote_count:
        header = (Fore.YELLOW, Style.BRIGHT, path, Style.RESET_ALL,)
        header += (' ', Fore.LIGHTBLACK_EX, '[ ',)
        header += (active_branch, format_count(local_count, Fore.LIGHTRED_EX, Fore.LIGHTBLACK_EX),)
        header += (' -> ',)
        header += (tracking_branch, format_count(remote_count, Fore.LIGHTGREEN_EX, Fore.LIGHTBLACK_EX),)

        for remote in repo.remotes:
            if remote.name == 'upstream':
                upstream_branch = join_path(remote.name, active_branch.name)
                upstream_count = len(list(repo.iter_commits('{}..{}'.format(tracking_branch, upstream_branch))))
                header += (' -> ',)
                header += (upstream_branch, format_count(remote_count, Fore.LIGHTGREEN_EX, Fore.LIGHTBLACK_EX),)
                break

        header += (' ]',)

        print(*header, Style.RESET_ALL, sep='')
        return True
    return False


def get_repositories_branches(repositories):
    for path, repo, remotes, extras in iter_repositories(repositories):
        print_repo_header(path, repo)


def run_jupyter_notebook():
    from unittest.mock import patch
    with patch.object(sys, 'argv', ["jupyter", "notebook"]):
        from jupyter_core.command import main as jupyter
        jupyter()


def get_argument_parser():
    parser = argparse.ArgumentParser(prog='bin/bdk')

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    init = subparsers.add_parser('init', help='''Initialize all configured repositories.''')
    sync = subparsers.add_parser('fetch', help='''Fetches new revisions from all remotes.''')
    status = subparsers.add_parser('status', aliases=('st',),
                                   help='''Display git status for all modified repositories.''')
    status.add_argument('filter', nargs='?')
    branch = subparsers.add_parser('branch', aliases=('br',), help='''Show active branch of all repositories.''')
    notebook = subparsers.add_parser('notebook', aliases=('nb', ), help='''Runs jupyter notebook.''')

    return parser


def main():
    parser = get_argument_parser()
    options = parser.parse_args()

    config = load_configuration()
    repositories = config.get('repositories', [])

    if options.command in ('init',):
        create_or_update_repositories(repositories)
    elif options.command in ('fetch',):
        create_or_update_repositories(repositories, sync=True)
    elif options.command in ('status', 'st'):
        get_repositories_status(repositories, filter_=options.filter)
    elif options.command in ('branch', 'br'):
        get_repositories_branches(repositories)
    elif options.command in ('notebook', 'nb'):
        run_jupyter_notebook()
    else:
        raise Exception('Unknown command.')

    if len(tasks):
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            for task in tasks:
                executor.submit(task)


if __name__ == '__main__':
    main()
