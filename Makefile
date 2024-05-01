run: # test with basic backup operation
	python diffsanity.py check fakeroot/src/ fakeroot/backup/

compile: # compile requirements with uv
	uv pip compile requirements.in >requirements.txt

help: # show help for each of the Makefile recipes
	@grep -E '^[a-zA-Z0-9 -]+:.*#'  Makefile | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done

# `make help` idea: see https://dwmkerr.com/makefile-help-command/
