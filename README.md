[![Python lint and CI/CD](https://github.com/chatbot-smooth/menuflow/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/chatbot-smooth/menuflow/actions/workflows/main.yml) 

![](https://komarev.com/ghpvc/?username=menuflow&label=VIEWS&style=for-the-badge&color=green)

# Menuflow

Menuflow is a project that is used in the matrix ecosystem, it allows to design conversation flows that will make users interacting with it to be fully guided in a conversation.

With Menuflow you can make connections to `REST APIs` through the `HTTP` protocol, control access tokens and update them dynamically. Messages can be customized using [Jinja](https://jinja.palletsprojects.com/en/3.1.x/), variables can be stored using postgres, variables will be stored for each room where they can then be used in the conversation.

<br>

---

## _Matrix room_ : [#menuflow:bramen.com.co](https://matrix.to/#/#menuflow:bramen.com.co)

---


<br>


# Setup menuflow

Requisitos:

- Base de datos postgres (Espero a futuro soportemos `sqlite`)
- Un servidor matrix, preferiblemnte `Synapse`, es el en que este proyecto fue construido

Opcionalmnete: 

- Un bridge (`WhatsApp`, `Instagram`, `Telegram` ...)

## Corre este proyecto con python:

- Copia el archivo de configuracion de ejemplo
```bash
cp menuflow/example-config.yaml config.yaml
```

- Configuralo segun tus necesidades:
```bash
vim config.yaml
```

- Instala los requerimientos: (Preferiblemnete en un entorno de desarrollo de python):
```bash
pip install -r requirements.txt
```

- Ahora puedes arrancar el proyecto:
```bash
python -m menuflow
```

## Corre este proyecto con Docker:

- Levante el contenedor: Esto generara el archivo config.yaml
```bash
docker run --rm -v `pwd`:/data:z bramenn/menuflow:latest`
```

- Configuralo segun tus necesidades:
```bash
vim config.yaml
```

- Ahora puedes arrancar el proyecto:
```bash
docker run --restart unless-stopped -v `pwd`:/data:z -p 24900:24900 bramenn/
menuflow:latest
```

## Corre este proyecto con docker-compose: Muy muy simple, solo mira

  - Levanta los servicios:
```bash
docker-compose up -d
```

## Registrar un bot: 
Para esto necesitamos el homeserver y el token del usuario de matrix que queremos registrar.

```bash
curl -XPOST -d {"homeserver":"https://matrix.exmaple.com", "access_token": "xyz"}' "http://menuflow_service/_matrix/menuflow/v1/client/new
```

## Configura un flujo:
Un flujo es un archivo `.yaml` que contiene las instruciones que un bot va seguir.

```yaml
menu:
  
  flow_variables:
    cat_url: "https://catfact.ninja/fact"

  nodes:

    - id: start
      type: message
      text: "Hello, this a flow sample, we have to some iteratios"
      o_connection: inpunt_1

    - id: inpunt_1
      type: input
      text: "Could yo enter your name?"
      variable: "username"
      validation: "{{username}}"
      cases:
        - id: default
          o_connection: inpunt_2

    - id: inpunt_2
      type: input
      text: "Could yo enter your phone number?"
      variable: "phone_number"
      validation: "{% set aux = product_option | string %}{%if aux.isdigit() %}True{% else %}False{% endif %}"
      cases:
        - id: "True"
          o_connection: inpunt_3
        - id: "False"
          o_connection: inpunt_2
        - id: default
          o_connection: error
          variables:
            error_msg: "Oops, something went wrong when you were entering your phone number"

    - id: inpunt_2
      type: input
      text: "Could yo enter your cat name?"
      inactivity_options:
        chat_timeout: 20 
        warning_message: "Please enter you cat name"
        time_between_attempts: 10 
        attempts: 3
      variable: "catname"
      validation: "{{catname}}"
      cases:
        - id: default
          o_connection: request_1
        - id: timeout
          o_connection: error
          variables:
            error_message: "No ingresaste el nombre de tu gato"

    - id: request_1
      type: http_request
      method: GET
      url: "{{cat_url}}"
      variables:
          fact_cat: fact
      cases:
      - id: 200
        o_connection: end_message
      - id: 500
        o_connection: error_api_cat
      - id: default
        o_connection: error
        variables:
            error_msg: "Oops, something went wrong when you were making the http request."
        

    - id: end_message
      type: message
      text: "{{username}} your phone number is {{phone_number}}<br> Ohh cierto, the your cat name is {{catname}}, and I'll tell you something about cats: _{{fact_cat}}_"
    
    - id: error
      type: message
      text: "{{error_message}}"

```
