all: compile lint format isort # all tools

# -- runs --

run: run-data # default run

run-data: # test with basic check against real data
	python diffsanity.py check fakeroot/src/ fakeroot/backup/

run-report: # test with basic check, plus report file option
	python diffsanity.py check --report missing.txt fakeroot/src/ fakeroot/backup/

# -- tools --

compile: # compile requirements with uv
	uv pip compile requirements.in >requirements.txt

TEMP_FILE := $(shell mktemp)
compile-dev: requirements.in requirements-dev.in # compile requirements for dev venv
	cat requirements.in requirements-dev.in >$(TEMP_FILE) | uv pip compile $(TEMP_FILE) >requirements-dev.txt

.PHONY: devenv
SHELL := /bin/bash
devenv:
	uv venv devenv
	uv pip install -r requirements-dev.txt
	@echo "Done."
	@echo
	@echo "Activate devenv:"
	@echo "  source devenv/bin/activate"
	@echo
	@echo "Then, run ipython:"
	@echo "  ipython"

lint: # ruff check tool
	ruff check diffsanity.py

format: # ruff format tool
	ruff format diffsanity.py

isort: # isort tool
	isort diffsanity.py

help: # show help for each of the Makefile recipes
	@grep -E '^[a-zA-Z0-9 -]+:.*#'  Makefile | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done

# `make help` idea: see https://dwmkerr.com/makefile-help-command/
