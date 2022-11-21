from datetime import datetime

from jinja2 import Environment

jinja_env = Environment(autoescape=True)

jinja_env.globals.update(date_isoformat=lambda: datetime.utcnow().isoformat())
