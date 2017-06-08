import git
import jinja2
import os
import yaml

def load_configuration():
    with open('config.yml') as f:
        template = jinja2.Template(f.read())

    source = template.render(github_username=os.environ.get('GITHUB_USERNAME', 'hartym'))
    config = yaml.load(source)

    return config

def create_or_update_repositories(repositories):
    packages = []
    for repository in repositories:
        assert len(repository) == 1
        path, remotes = list(repository.items())[0]
        assert 'origin' in remotes

        extras = remotes.pop('extras', '')

        if not os.path.exists(path):
            os.system('git clone '+remotes['origin']+' '+path)

        repo = git.Repo(path)

        # update the remotes if the url does not match the config
        for remote in repo.remotes:
            if remote.name in remotes and remote.url != remotes[remote.name]:
                remote.set_url(remotes[remote.name])
                remote.fetch(tags=True)
            remotes.pop(remote.name)

        # add missing remotes
        for remote, url in remotes.items():
            repo.create_remote(remote, url).fetch(tags=True)

        packages.append('-e {}{}'.format(path, '['+extras+']' if extras else ''))

    with open('.requirements.local.txt', 'w+') as f:
        f.write('\n'.join(packages))

def main():
    config = load_configuration()
    create_or_update_repositories(config.get('repositories', []))

if __name__ == '__main__':
    main()
