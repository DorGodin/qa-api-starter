# One image, two roles: it serves the demo API, and it runs the suites against it.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY . .

CMD ["python", "-m", "uvicorn", "demo_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
