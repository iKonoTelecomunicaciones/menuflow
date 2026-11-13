#==================================== Builder Stage ==========================================
FROM python:3.12.3-slim AS builder

WORKDIR /opt/menuflow

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libmagic1 \
      git \
      inotify-tools \
      jq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py requirements-dev.txt README.md ./
COPY menuflow ./menuflow

RUN --mount=type=bind,source=.git,target=/opt/menuflow/.git \
    python setup.py --version && \
    pip install --no-cache-dir --no-deps .


#==================================== Dev Stage ==========================================
FROM builder AS dev

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . /opt/menuflow

CMD ["/opt/menuflow/run.sh", "dev"]

#==================================== Runtime Stage ==========================================
FROM python:3.12.3-slim AS runtime

WORKDIR /opt/menuflow

RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 jq && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/menuflow/menuflow ./menuflow
COPY --from=builder /opt/menuflow/menuflow/example-config.yaml ./
COPY run.sh LICENSE ./

VOLUME [ "/data" ]

CMD ["/opt/menuflow/run.sh"]
