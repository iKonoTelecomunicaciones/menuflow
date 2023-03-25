[![Python lint and CI/CD](https://github.com/chatbot-smooth/menuflow/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/chatbot-smooth/menuflow/actions/workflows/main.yml) 

![](https://komarev.com/ghpvc/?username=menuflow&label=VIEWS&style=for-the-badge&color=green)

# Menuflow

Menuflow es un proyecto que se utiliza en el ecosistema matrix, permite diseñar flujos de conversación que harán que los usuarios que interactúen con él sean totalmente guiados en una conversación.

Con Menuflow se pueden realizar conexiones a `REST APIs` a través del protocolo `HTTP`, controlar los tokens de acceso y actualizarlos dinámicamente. Los mensajes pueden ser personalizados usando [Jinja](https://jinja.palletsprojects.com/en/3.1.x/), las variables pueden ser almacenadas usando postgres, las variables serán almacenadas para cada sala donde luego podrán ser usadas en la conversación.

---

### _**Matrix room**_ : [#menuflow:bramen.com.co](https://matrix.to/#/#menuflow:bramen.com.co)

---

<br>

## Algunas imágenes de ejemplo:

- Conversar con el bot (en este caso usando el bridge de WhatsApp)

![image](https://user-images.githubusercontent.com/50601186/188774939-0d282706-b085-4906-8f37-f8427f767d07.png)

---

<br>

- Y puedes formatear mensajes usando la sintaxis de Jinja:

```yaml
    - id: 'm1'
      type: 'message'
      text: "
              {% for new to news %}

                {% if loop.index0 < 3%}
                  {% set _new = news|random%}
                  ---<br>
                  **Title**: {{_new['title']}}<br>
                  **Author**: {{_new['author']}}<br>
                  **Date**: {{_new['date']}}<br>
                  **Image**: {{_new['imageUrl']}}<br>
                  {{_new['content']}}<br><br>
                {% will end if%}
              {% endfor%}
            "
      o_connection: 'm2'
```


![image](https://user-images.githubusercontent.com/50601186/192087256-9aff9f3c-ee0b-4d27-92c1-57bba7b0fe2b.png)

<br>

# Setup menuflow

Requisitos:

- Base de datos postgres (Espero a futuro soportemos `sqlite`)
- Un servidor matrix, preferiblemente `Synapse`,  este proyecto fue construido sobre este servidor.

Opcionalmente: 

- Un bridge (`WhatsApp`, `Instagram`, `Telegram` ...)

## Corre este proyecto con python:

- Copia el archivo de configuración de ejemplo
```bash
cp menuflow/example-config.yaml config.yaml
```

- Configúralo según tus necesidades:
```bash
vim config.yaml
```

- Instala los requerimientos: (Preferiblemente en un entorno de desarrollo de python):
```bash
pip install -r requirements.txt
```

- Ahora puedes arrancar el proyecto:
```bash
python -m menuflow
```

## Corre este proyecto con Docker:

- Levante el contenedor: Esto generará el archivo config.yaml
```bash
docker run --rm -v `pwd`:/data:z bramenn/menuflow:latest`
```

- Configúralo según tus necesidades:
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
Un flujo es un archivo `.yaml` que contiene las instrucciones que un bot va a seguir. Para más información sobre cada uno de los nodos, vea a: https://github.com/chatbot-smooth/menuflow/wiki#nodes

```yaml
menu:
    
  flow_variables:
    cat_fatc_url: 'https://catfact.ninja/fact'

  nodes:

    - id: start
      type: message
      text: 'Hello, this a flow sample. {{foo}}'
      o_connection: input-1

    - id: input-1
      type: input
      text: 'Do you have 1 or more cats?, please enter (y/n)'
      variable: has_cats
      validation: '{{ has_cats }}'
      inactivity_options:
        chat_timeout: 20
        warning_message: 'Please enter an option, or the menu will end.'
        time_between_attempts: 10
        attempts: 3
      cases:
        - id: 'y'
          o_connection: input-2
        - id: 'n'
          o_connection: last-message
          variable:
            no_cats: 'You are a user without cats, without life, without happiness ...'
        - id: timeout
          o_connection: last-message

    - id: input-2
      type: input
      text: 'Enter your cat''s name:'
      variable: cat_name
      validation: '{{ cat_name }}'
      cases:
        - id: default
          o_connection: input-3

    - id: input-3
      type: input
      text: 'Enter your cat''s age in months:'
      variable: cat_age
      validation: >-
        {% set aux = cat_age | string %}{% if aux.isdigit()
        %}True{%else%}False{% endif %}
      cases:
        - id: 'True'
          o_connection: switch-1
        - id: default
          o_connection: input-3

    - id: switch-1
      type: switch
      validation: >-
        {% set aux = cat_age %}{% set aux = aux | int %}{% if aux < 12
        %}ok{%elif not cat_age.isdigit() %}{% else %}ko{% endif %}
      cases:
        - id: ok
          o_connection: request-1
          variables:
            cat_message: Your cat is a puppy
        - id: ko
          o_connection: request-1
          variables:
            cat_message: Your cat is an adult

    - id: request-1
      type: http_request
      method: GET
      url: '{{cat_fatc_url}}'
      variables:
        cat_fact: fact
      cases:
        - id: '200'
          o_connection: message-2
        - id: default
          o_connection: error-message-1

    - id: message-2
      type: message
      text: >-
        {{cat_message}}, also let me give you an interesting fact about cats.
        Did you know that cats: **{{ cat_fact }}**
      o_connection: message-3

    - id: message-3
      type: message
      text: I'm going to share with you a picture of a kitten
      o_connection: media-1

    - id: media-1
      type: media
      message_type: m.image
      text: A cat
      url: 'https://cataas.com/cat'
      o_connection: input-4

    - id: input-4
      type: input
      text: 'Ahora tu ingresa la imagen de tu gato:'
      input_type: m.image
      variable: user_cat_image
      cases:
        - id: true
          o_connection: last-message
        - id: false
          o_connection: input-3

    - id: last-message
      type: message
      text: 'Bye bye! ... {{no_cats}}'

    - id: error-message-1
      type: message
      text: 'Algo ha salido mal, bye'
```
