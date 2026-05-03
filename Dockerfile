FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NIL_ARTIFACTS_DIR=/app/artifacts

COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install -e ".[api]"

# Bake training so the image ships with artifacts; override at run time
# by mounting a volume on /app/artifacts if you train externally.
RUN nil-train --n 10000 --seed 7 --out /app/artifacts

EXPOSE 8000
CMD ["uvicorn", "nil_predictor.api:app", "--host", "0.0.0.0", "--port", "8000"]
