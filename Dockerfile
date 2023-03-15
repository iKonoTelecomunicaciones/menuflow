FROM alpine:3.17

RUN apk add --no-cache \
      python3 py3-pip py3-setuptools py3-wheel \
      py3-pillow \
      py3-virtualenv \
      py3-aiohttp \
      py3-magic \
      py3-ruamel.yaml \
      py3-commonmark \
      bash \
      su-exec

COPY requirements.txt /opt/menuflow/requirements.txt
WORKDIR /opt/menuflow
RUN apk add --virtual .build-deps python3-dev libffi-dev build-base \
 && pip install --upgrade pip \
 && pip3 install -r requirements.txt \
 && apk del .build-deps

COPY . /opt/menuflow
RUN cp menuflow/example-config.yaml .

VOLUME /data

CMD ["/opt/menuflow/run.sh"]
