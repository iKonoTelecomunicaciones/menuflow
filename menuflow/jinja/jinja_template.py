from datetime import datetime

from jinja2 import Environment

jj_env = Environment(autoescape=True)

jj_env.globals.update(date_isoformat=lambda: datetime.utcnow().isoformat())
