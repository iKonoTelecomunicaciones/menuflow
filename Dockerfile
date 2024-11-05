FROM alpine:3.18

RUN apk add --no-cache \
      python3 py3-pip py3-setuptools py3-wheel \
      py3-pillow \
      py3-virtualenv \
      py3-aiohttp \
      py3-magic \
      py3-ruamel.yaml \
      py3-commonmark \
      bash \
      curl \
      su-exec

COPY requirements.txt /opt/menuflow/requirements.txt
WORKDIR /opt/menuflow
RUN apk add --virtual .build-deps python3-dev libffi-dev build-base \
      && pip install --upgrade pip \
      && pip3 install -r requirements.txt \
      && apk del .build-deps

COPY . /opt/menuflow
RUN apk add --no-cache git \
      && python3 setup.py --version \
      && pip3 install .[all] \
      && cp menuflow/example-config.yaml . \
      && rm -rf menuflow .git build

VOLUME /data

CMD ["/opt/menuflow/run.sh"]
