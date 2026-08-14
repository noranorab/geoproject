FROM ghcr.io/osgeo/gdal:ubuntu-small-3.8.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --break-system-packages -e .

EXPOSE 8000

CMD ["uvicorn", "wildfirewatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
