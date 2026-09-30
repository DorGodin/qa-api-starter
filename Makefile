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

perf-smoke:     ## one user, seconds, gates every merge
	k6 run perf/smoke.js

# Each perf target names its own PROFILE so none of them depends on k6 flag
# order. PROFILE= on the command line still overrides perf-load and perf-write.
K6FLAGS = -e VUS=$(or $(VUS),10) -e RAMP=$(or $(RAMP),10s) -e HOLD=$(or $(HOLD),20s)

perf-load:      ## read path under concurrency; override VUS, RAMP, HOLD, PROFILE
	k6 run $(K6FLAGS) -e PROFILE=$(or $(PROFILE),load) perf/load.js

perf-write:     ## write path under concurrency - create + submit, money math asserted
	k6 run $(K6FLAGS) -e PROFILE=$(or $(PROFILE),load) perf/write_path.js

perf-spike:     ## sudden 5x jump on the write path, then recovery
	k6 run $(K6FLAGS) -e PROFILE=spike perf/write_path.js

perf-soak:      ## long hold, looking for leaks; override HOLD (default 10m)
	k6 run $(K6FLAGS) -e PROFILE=soak perf/write_path.js

perf-stress:    ## ramp past capacity to find the ceiling; only 5xx fails the run
	k6 run $(K6FLAGS) -e PROFILE=stress perf/write_path.js

perf:           ## everything except soak and stress - the pre-release set
	$(MAKE) perf-smoke && $(MAKE) perf-load && $(MAKE) perf-write

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
