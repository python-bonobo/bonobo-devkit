PWD ?= $(shell pwd)
PACKAGE ?= bonobo
PACKAGES ?= bonobo bonobo-docker bonobo-sqlalchemy
IMPORT ?= $(subst -,_,$(PACKAGE))
IMPORTS ?= $(subst -,_,$(PACKAGES))
PYTHON_VERSION ?= 3.5
PYTHON_VERSIONS ?= 3.5 3.6
PYTHON_BASE ?= $(PWD)/.envs/bonobo$(PYTHON_VERSION)
PYTHON_BIN ?= $(PYTHON_BASE)/bin
PYTHON_PIP ?= $(PYTHON_BIN)/pip$(PYTHON_VERSION)
PYTHON ?= $(PYTHON_BIN)/python$(PYTHON_VERSION)
PYTEST ?= $(PYTHON_BIN)/pytest
PYTEST_OPTIONS ?= --capture=no
TWINE ?= $(PYTHON_BIN)/twine
VERSION := $(shell $(PYTHON) $(PACKAGE)/setup.py --version)

RELEASE_TARGETS := $(foreach p,$(PACKAGES),$(foreach v,$(PYTHON_VERSIONS),release-$p-$v))
UPLOAD_TARGETS := $(addprefix upload-,$(PACKAGES))

.PHONY: all clean cleanenv install release release-one $(RELEASE_TARGETS) upload upload-one $(UPLOAD_TARGETS) test

all:
	$(foreach PYTHON_VERSION,$(PYTHON_VERSIONS),PYTHON_VERSION=$(PYTHON_VERSION) $(MAKE) install;)

install: $(PYTHON_BASE)
	$(PYTHON_PIP) install -r requirements.txt

clean:
	rm -rf ./output ./.release

cleanenv:
	rm -rf ./.envs

release: $(RELEASE_TARGETS)

$(RELEASE_TARGETS): release-%:
	-$(MAKE) release-one `echo $* | sed 's/^\(.*\)-\(3\.[0-9]\)$$/PACKAGE=\1 PYTHON_VERSION=\2/g'`

release-one: output
	$(eval TMP := $(shell mktemp -d))
	@echo "Cooking $(PACKAGE) $(VERSION) release (in $(TMP))"
	@(cd $(PACKAGE); git rev-parse $(VERSION))
	@(cd $(PACKAGE); git archive `git rev-parse $(VERSION)`) | tar xf - -C $(TMP)
	@(cd output; $(PYTHON) $(TMP)/setup.py sdist bdist_egg bdist_wheel > /dev/null)
	@rm -rf $(TMP)

upload: $(UPLOAD_TARGETS)

$(UPLOAD_TARGETS): upload-%:
	-$(MAKE) upload-one PACKAGE=$*

upload-one:
	twine upload --skip-existing output/dist/$(IMPORT)-$(VERSION)*

output:
	mkdir -p output

test:
	$(PYTEST) $(PYTEST_OPTIONS) bonobo/tests bonobo-sqlalchemy/tests --cov=bonobo --cov=bonobo_sqlalchemy --cov-report html

$(PYTHON_BASE):
	virtualenv -p python$(PYTHON_VERSION) $@
