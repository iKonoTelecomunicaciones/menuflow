from jinja2 import BaseLoader, Environment
from jinja2_ansible_filters import AnsibleCoreFiltersExtension

from .filters import register_filters
from .globals import register_globals
from .matrix_filters import MatrixFilters
from .tests import register_tests

jinja_env = Environment(
    autoescape=True,
    loader=BaseLoader,
    extensions=[
        AnsibleCoreFiltersExtension,
        MatrixFilters,
        "jinja2.ext.debug",
        "jinja2.ext.do",
        "jinja2.ext.loopcontrols",
    ],
)

register_globals(jinja_env)
register_filters(jinja_env)
register_tests(jinja_env)
