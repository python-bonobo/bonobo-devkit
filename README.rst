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
* Run `make` (will create two virtualenv, clone the needed repositories and setup the correct remotes).

Just run make to build 2 virtualenvs (3.5 and 3.6) with all bonobo packages installed as editable.

`source activate3.5` or `source activate3.6` to activate a given virtualenv in your current shell.

