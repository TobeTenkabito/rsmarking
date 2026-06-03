# text slim text
FROM python:3.10-slim
ARG RS_SANDBOX_SPEC_HASH=unknown
LABEL rsmarking.sandbox.spec_hash=$RS_SANDBOX_SPEC_HASH

# text,text .pyc text,text
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# text (GDAL text)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# text
RUN pip install --no-cache-dir \
    affine \
    imageio \
    matplotlib \
    numpy \
    numexpr \
    opencv-python-headless \
    pillow \
    pyproj \
    scipy \
    rasterio \
    scikit-image \
    scikit-learn \
    shapely \
    tifffile

# text root text(text)
RUN useradd -m -s /bin/bash sandboxuser
WORKDIR /app

# text
COPY sandbox_entry.py /app/sandbox_entry.py
RUN chown sandboxuser:sandboxuser /app/sandbox_entry.py && chmod +x /app/sandbox_entry.py

# text root text
USER sandboxuser

# text
ENTRYPOINT ["python", "/app/sandbox_entry.py"]
