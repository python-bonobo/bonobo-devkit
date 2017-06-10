bonobo-devkit
=============

A convenience repository containing all tools to work efficiently on bonobo and its extensions.

Requirements
::::::::::::

* `virtualenv`, `python3.5` and `python3.6` should be accessible from path.
* Github access using ssl should be possible. You don't need r/w access to bonobo repository, but your ssh key should
  allow some access to github.

Setup
:::::

* Setup your github username if not done yet: `git config --global github.user hartym`
* Run `make` (will create two virtualenv, clone the needed repositories, setup the correct remotes and install all
  packages as editable in both virtualenv).

Once this is done, a helper script is available in `bin/bdk` to work on multiple repositories at once:

* `bin/bdk init`: lightweight fetch used by `make install` to do the initial setup.
* `bin/bdk fetch`: will fetch all new objects from git remotes (both upstream and origin, and more if you setup more).
* `bin/bdk branch`: show which branch each repository is pointing at.
* `bin/bdk status`: show a `git status` like output on all repositories to have a quick overview of changes.

Tracked repositories are configured in `config.yml`, and optionnaly extended/overriden by `config.local.yml`. The file
content is parsed using jinja2, then should be valid yaml. Local version will extend yaml lists and the dicts will be
merged "deeply", so you can add new repositories, new remotes, or override a value in the local file.

Working
:::::::

`source activate3.5` or `source activate3.6` to activate a given virtualenv in your current shell.



