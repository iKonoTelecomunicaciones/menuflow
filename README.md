# Proposals

## Variables:

## Nodes:

##### Messages:
- `TODO` Knowing when a message should wait and when to continue the flow
- `TODO` Ability to create custom jinja filters
- `TODO` The texts that will be displayed, can be generated with jinja templates

##### Request:
- `TODO` Support http request nodes

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

