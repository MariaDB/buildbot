VENV_DIR := .venv
VENDOR_DIR := .vendor
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
.SHELLFLAGS := -eu -o pipefail -c
PATH := $(VENV_DIR)/bin:$(PATH)
export PATH

help:
	@grep -E '^[a-zA-Z1-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN { FS = ":.*?## " }; { printf "\033[36m%-30s\033[0m %s\n", $$1, $$2 }'

venv: ## Create python3 venv if it does not exists
	$(info --> Create python virtual env ($(VENV_DIR)))
	[[ -d $(VENV_DIR) ]] || $(shell command -v python3) -m venv $(VENV_DIR)
	@echo -e "\n--> You should now activate the python3 venv with:"
	@echo -e "source $(VENV_DIR)/bin/activate"

install-pre-commit: ## Install pre-commit tool
	$(info --> Install pre-commit tool via `pip3`)
	pip3 install pre-commit

pre-commit-run: ## Run pre-commit hooks with $PRE_COMMIT_ARGS default to (diff master...[current_branch])
	$(info --> run pre-commit on changed files (pre-commit run))
	pre-commit run $(PRE_COMMIT_ARGS) --color=always

pre-commit-run-all: ## Run pre-commit on the whole repository
	$(info --> run pre-commit on the whole repo (pre-commit run -a))
	pre-commit run -a --color=always

checkconfig: ## Validate master.cfg files
	$(info --> validate master.cfg files with docker)
	./validate_master_cfg.sh
