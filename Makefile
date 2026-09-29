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

perf-load:      ## concurrency on the read path; override VUS, RAMP, HOLD
	k6 run -e VUS=$(or $(VUS),10) -e RAMP=$(or $(RAMP),10s) -e HOLD=$(or $(HOLD),20s) perf/load.js

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
