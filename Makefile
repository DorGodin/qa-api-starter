VENV ?= .venv
PY   := $(VENV)/bin/python
ENV  ?= local

.PHONY: install api test unit edge all lock clean

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.lock.txt

api:            ## run the demo API this repo tests against
	ENV=$(ENV) $(PY) -m uvicorn demo_api.app:app --host 127.0.0.1 --port 8000

test:           ## product behaviour suites (needs the API running)
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest

unit:           ## framework's own tests, no API, no network
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --unit tests/unit

edge:           ## validation edge cases
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --edge-cases

all:
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --unit --edge-cases

lock:
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip freeze > requirements.lock.txt

clean:
	rm -rf .pytest_cache **/__pycache__

env-check:      ## prove ENV is usable: config, health, a login per persona. Read-only
	ENV=$(ENV) $(PY) scripts/env_check.py

# Every perf target goes through scripts/perf_run.py: k6's own output is shown
# unchanged, and the result is appended to reports/perf.jsonl even when a
# threshold is crossed - those are the runs worth having in the history.
#
# Each target names its own profile and its own HOLD default, so none of them
# depends on k6 honouring the last of two duplicate -e flags. Soak in particular
# must not inherit the 20s default: a 20 second soak cannot find a leak.
PERF    = $(PY) scripts/perf_run.py
K6RAMP  = -e VUS=$(or $(VUS),10) -e RAMP=$(or $(RAMP),10s)
K6FLAGS = $(K6RAMP) -e HOLD=$(or $(HOLD),20s)

perf-smoke:     ## one user, seconds, gates every merge
	$(PERF) perf/smoke.js --profile smoke

perf-load:      ## read path under concurrency; override VUS, RAMP, HOLD, PROFILE
	$(PERF) perf/load.js --profile $(or $(PROFILE),load) $(K6FLAGS)

perf-write:     ## write path under concurrency - create + submit, money math asserted
	$(PERF) perf/write_path.js --profile $(or $(PROFILE),load) $(K6FLAGS)

perf-spike:     ## sudden 5x jump on the write path, then recovery
	$(PERF) perf/write_path.js --profile spike $(K6FLAGS)

perf-soak:      ## long hold, looking for leaks; override HOLD (default 10m)
	$(PERF) perf/write_path.js --profile soak $(K6RAMP) -e HOLD=$(or $(HOLD),10m)

perf-stress:    ## ramp past capacity to find the ceiling; only 5xx fails the run
	$(PERF) perf/write_path.js --profile stress $(K6FLAGS)

perf:           ## everything except soak and stress - the pre-release set
	$(MAKE) perf-smoke && $(MAKE) perf-load && $(MAKE) perf-write

perf-trends:    ## what moved against earlier perf runs of the same shape
	$(PY) scripts/perf_trends.py

ui:             ## browser suite (needs: playwright install chromium)
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --ui tests/ui

llm:            ## LLM evaluation with DeepEval, deterministic metrics, no API key
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --llm tests/llm

docker-test:    ## run the suites in containers, no local Python needed
	docker compose run --rm tests

docker-ui:      ## run the browser suite in a container with browsers preinstalled
	docker compose run --rm ui

docker-api:     ## just the API, on http://127.0.0.1:8000
	docker compose up --build api

docker-down:
	docker compose down -v

security:       ## access control and exposure checks
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --security tests/security

report:         ## show the report from the last run
	@cat reports/last-run.md

dashboard:      ## build reports/dashboard.html from the run history and the artifact ledger
	$(PY) scripts/dashboard.py

trends:         ## compare the last run against the ones before it
	$(PY) scripts/trends.py

cleanup:        ## show what the runs created on ENV; add YES=1 to delete
	$(PY) scripts/cleanup.py --env $(ENV) $(if $(YES),--yes,)

hooks:          ## install the pre-commit hooks (secrets, lint, whitespace)
	$(VENV)/bin/pip install -q pre-commit
	$(VENV)/bin/pre-commit install
	@echo "hooks installed. Run them on everything once with: $(VENV)/bin/pre-commit run --all-files"

notify-dry:     ## show the run summary that would be posted
	ENV=$(ENV) PYTHONPATH=. $(PY) -m pytest --notify-dry-run
