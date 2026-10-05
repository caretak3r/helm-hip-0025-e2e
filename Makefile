# HIP-0025 black-box tests. `make help` lists the targets.

TIERS ?= pr1,pr2,pr3,combined
ARGS  ?=
RUN   ?=
PY    := uv run python

.PHONY: help run build report site serve cluster cluster-down lint clean

help:
	@echo "make run                   Fetch the PR commits, build one helm per tier, run the Go unit"
	@echo "                           tests and the cluster tests, write runs/<stamp>/"
	@echo "make run TIERS=pr1,pr3     Test only these tiers (pr1, pr2, pr3, combined)"
	@echo "make run ARGS='-k groups'  Give more arguments to pytest"
	@echo "make build                 Build the helm binaries only (.bin/helm-<tier>)"
	@echo "make report [RUN=<dir>]    Write REPORT.md again (default: the newest run)"
	@echo "make site                  Build the dashboard from runs/ into site/"
	@echo "make serve                 Build the dashboard and serve it on http://127.0.0.1:8000"
	@echo "make cluster               Create the kind cluster with audit logging"
	@echo "make cluster-down          Delete the kind cluster"
	@echo "make lint                  Lint the Python code and the shell scripts"
	@echo "make clean                 Remove .work/, .bin/ and site/"

run:
	@$(PY) e2e/run.py run --tiers $(TIERS) $(if $(ARGS),-- $(ARGS))

build:
	@$(PY) e2e/run.py build --tiers $(TIERS)

report:
	@$(PY) e2e/run.py report $(if $(RUN),--run $(RUN))

site:
	@$(PY) -m testgrid build --runs runs --out site

serve: site
	@$(PY) -m http.server 8000 --bind 127.0.0.1 --directory site

cluster:
	@bash scripts/cluster-up.sh

cluster-down:
	@bash scripts/cluster-down.sh

lint:
	@uv run --group dev ruff check e2e testgrid
	@for s in scripts/*.sh; do bash -n "$$s"; done

clean:
	rm -rf .work .bin site
