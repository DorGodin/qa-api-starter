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
