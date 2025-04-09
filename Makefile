VENV_DIR := .venv
VENDOR_DIR := .vendor
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
.SHELLFLAGS := -eu -o pipefail -c
PATH := $(VENV_DIR)/bin:$(PATH)
WWW_PKGS := www/base www/console_view www/grid_view www/waterfall_view www/wsgi_dashboards www/badges
WWW_DEP_PKGS := www/guanlecoja-ui www/data_module
UV_PYTHON := 3.9
export PATH
export UV_PYTHON

help:
	@grep -E '^[a-zA-Z1-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN { FS = ":.*?## " }; { printf "\033[36m%-30s\033[0m %s\n", $$1, $$2 }'

install: ## Install all necessary tools
	$(MAKE) venv
	$(MAKE) install-pip-packages
	$(MAKE) install-vlad-bb-fork
	@echo -e "\n--> You should now activate the python3 venv with:"
	@echo -e "source $(VENV_DIR)/bin/activate\n"

venv: ## Create python3 venv if it does not exists
	$(info --> Create python virtual env ($(VENV_DIR)))
	[[ -d $(VENV_DIR) ]] || uv venv --seed $(VENV_DIR)
	@echo -e "\n--> You should now activate the python3 venv with:"
	@echo -e "source $(VENV_DIR)/bin/activate\n"

install-pip-packages: ## Install python3 requirements
	$(info --> Install requirements via `pip`)
	uv pip install -r requirements.txt

install-vlad-bb-fork: ## Install vlad bb fork
	$(info --> Install vlad's bb fork)
	@echo -e "\n--> Make sure to install following packages:"
	@echo -e "- libmariadb-dev"
	@echo -e "- libvirt-dev\n"
	if [[ ! -d $(VENDOR_DIR) ]]; then \
		source $(VENV_DIR)/bin/activate; \
		git clone --branch grid https://github.com/vladbogo/buildbot $(VENDOR_DIR); \
		cd $(VENDOR_DIR)/master && python setup.py bdist_wheel; \
		pip install ./dist/*.whl; \
	fi

install-pre-commit: ## Install pre-commit tool
	$(info --> Install pre-commit tool via `pip`)
	uv pip install pre-commit

pre-commit-run: ## Run pre-commit hooks with $PRE_COMMIT_ARGS default to (diff master...[current_branch])
	$(info --> run pre-commit on changed files (pre-commit run))
	pre-commit run $(PRE_COMMIT_ARGS) --color=always

pre-commit-run-all: ## Run pre-commit on the whole repository
	$(info --> run pre-commit on the whole repo (pre-commit run -a))
	pre-commit run -a --color=always

checkconfig: ## Validate master.cfg files
	$(info --> validate master.cfg files with docker)
	./validate_master_cfg.sh

test: ## Run unittests
	$(info --> run unittests)
	python -m unittest discover -s configuration/test -p "test*.py"

clean: ## Clean venv
	[[ ! -d $(VENV_DIR) ]] || rm -rf $(VENV_DIR)
	[[ ! -d $(VENDOR_DIR) ]] || rm -rf $(VENDOR_DIR)
