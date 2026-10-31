FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . /app/api/

# Copy model artifacts (mounted via volume in compose)
# ARTIFACTS_DIR env var points to the mounted path

ENV ARTIFACTS_DIR=/app/models/artifacts
ENV PORT=8000
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
