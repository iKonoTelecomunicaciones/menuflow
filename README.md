It works in the Matrix ecosystem.

If you want to create conversion flows and validate multiple options, print custom messages and access external APIs, Menuflow is a good choice for you.

MenuFlow allows you to create different Matrix client instances and each one customises a conversation flow.

This project was based on [maubot](https://github.com/maubot/maubot), built entirely with the [mautrix-python](https://github.com/mautrix/python) framework.

# Room to participate in the project
[#menuflow:bramen.com.co](https://matrix.to/#/#menuflow:bramen.com.co)


---
---

- An image explaining what this plugin does :)

![image](https://user-images.githubusercontent.com/50601186/188774939-0d282706-b085-4906-8f37-f8427f767d07.png)

- Print lists of variables and fomate them with jinja :v

These texts were obtained using the `http_request` node:
```yaml
    - id: 'r1'
      type: 'http_request'
      method: GET #POST
      URL: https://inshorts.deta.dev/news?category={{category}}

      variables:
        news: data

      cases:
        - id: 200
          o_connection: m4
        - id: default
          o_connection: m5
```

And formatted with jinja in a `message` node:

```yaml
    - id: 'm4'
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
      o_connection: 'm1'
```


![image](https://user-images.githubusercontent.com/50601186/192087256-9aff9f3c-ee0b-4d27-92c1-57bba7b0fe2b.png)
