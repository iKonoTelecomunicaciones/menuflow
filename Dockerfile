#==================================== Base Stage ==========================================
FROM python:3.12.3-slim AS base

WORKDIR /opt/menuflow

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3-pip \
      python3-setuptools \
      python3-wheel \
      libmagic1 \
      git \
      inotify-tools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade --no-cache-dir pip

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt


VOLUME [ "/data" ]

#==================================== Dev Stage ==========================================
FROM base AS dev

COPY requirements-dev.txt ./

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . /opt/menuflow

RUN python setup.py --version && \
    pip install --no-cache-dir .[all] && \
    cp menuflow/example-config.yaml . && \
    rm -rf .git build


CMD ["/opt/menuflow/run.sh", "dev"]
#==================================== Runtime Stage ==========================================
FROM base AS runtime

COPY . /opt/menuflow

RUN python setup.py --version && \
    pip install --no-cache-dir .[all] && \
    cp menuflow/example-config.yaml . && \
    rm -rf .git build

CMD ["/opt/menuflow/run.sh"]
