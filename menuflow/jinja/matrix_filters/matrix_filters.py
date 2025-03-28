import warnings

from jinja2 import Environment
from jinja2.ext import Extension

from .filters import user_bridge_account_id, user_bridge_info, user_bridge_prefix, user_homeserver


class MatrixFilters(Extension):
    def __init__(self, environment: Environment):
        super().__init__(environment)
        filters = self.filters()
        for x in filters:
            if x in environment.filters:
                warnings.warn(
                    "Filter name collision detected changing "
                    "filter name to ans_{0} "
                    "to avoid clobbering".format(x),
                    RuntimeWarning,
                )
                filters["ans_" + x] = filters[x]
                del filters[x]

        # Register provided filters
        environment.filters.update(filters)

    def filters(self):
        return {
            "user_bridge_info": user_bridge_info,
            "user_bridge_prefix": user_bridge_prefix,
            "user_bridge_account_id": user_bridge_account_id,
            "user_homeserver": user_homeserver,
        }
