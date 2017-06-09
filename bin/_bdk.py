import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import git
import jinja2
import yaml
from colorama import Fore, Style

try:
    from bonobo.logging import getLogger
except ImportError:
    from logging import getLogger

logger = getLogger('bdk')
tasks = []


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
    with open('config.yml') as f:
        template = jinja2.Template(f.read())
    source = template.render(github_username=os.environ.get('GITHUB_USERNAME', 'hartym'))
    config = yaml.load(source)

    if os.path.exists('config.local.yml'):
        with open('config.local.yml') as f:
            template = jinja2.Template(f.read())
        source = template.render(github_username=os.environ.get('GITHUB_USERNAME', 'hartym'))
        config = merge(config, yaml.load(source))

    return config


def create_or_update_repositories(repositories, sync=False):
    packages = []
    for repository in repositories:
        assert len(repository) == 1
        path, remotes = list(repository.items())[0]
        assert 'origin' in remotes

        extras = remotes.pop('extras', '')
        need_fetch = sync

        if not os.path.exists(path):
            logger.info('Cloning {} from {}'.format(path, remotes['origin']))
            os.system('git clone ' + remotes['origin'] + ' ' + path)

        repo = git.Repo(path)

        # update the remotes if the url does not match the config
        for remote in repo.remotes:
            if remote.name in remotes and remote.url != remotes[remote.name]:
                remote.set_url(remotes[remote.name])
                need_fetch = True
            remotes.pop(remote.name)

        # add missing remotes
        for remote, url in remotes.items():
            need_fetch = True
            repo.create_remote(remote, url)

        if need_fetch:
            for remote in repo.remotes:
                def task(path=path, remote=remote, logger=logger):
                    logger.info('Fetch begins: {} ({})'.format(path, remote.name))
                    remote.fetch(tags=True)
                    logger.info('Fetch complete: {} ({})'.format(path, remote.name))

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
    for repository in repositories:
        assert len(repository) == 1
        path, remotes = list(repository.items())[0]

        if filter_ and path != filter_:
            continue

        repo = git.Repo(path)

        if repo.is_dirty(untracked_files=True):
            print(Fore.YELLOW, Style.BRIGHT, '• ', path, Style.RESET_ALL, ' (' + str(repo.active_branch) + ')', sep='')
            for diff, name, color, reverse in (
                    (repo.index.diff(repo.head.commit), 'Changes to be committed:', Fore.GREEN, True),
                    (repo.index.diff(None), 'Changes not staged for commit:', Fore.RED, False),
                    (repo.untracked_files, 'Untracked files:', Fore.RED, False),):
                if len(diff):
                    print('  ', name)
                    print(color, '\n'.join(map(partial(format_diff, reverse=reverse), diff)), Fore.RESET, sep='')
            print()


def get_repositories_branches(repositories):
    for repository in repositories:
        assert len(repository) == 1
        path, remotes = list(repository.items())[0]
        repo = git.Repo(path)
        print(Fore.YELLOW, Style.BRIGHT, path, Style.RESET_ALL, ' ', repo.active_branch, sep='')
    pass


def get_argument_parser():
    parser = argparse.ArgumentParser(prog='bin/bdk')

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    init = subparsers.add_parser('init')
    sync = subparsers.add_parser('sync')
    status = subparsers.add_parser('status', aliases=('st',))
    status.add_argument('filter', nargs='?')
    branch = subparsers.add_parser('branch', aliases=('br',))

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
    else:
        raise Exception('Unknown command.')

    if len(tasks):
        with ThreadPoolExecutor(max_workers=4) as executor:
            for task in tasks:
                executor.submit(task)


if __name__ == '__main__':
    main()
