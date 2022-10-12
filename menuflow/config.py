import random
import string

from mautrix.util.config import BaseFileConfig, ConfigUpdateHelper


class Config(BaseFileConfig):
    @staticmethod
    def _new_token() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=64))

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        base = helper.base
        copy = helper.copy
        copy_dict = helper.copy_dict
        copy("menuflow.users_ignore")
        copy("menuflow.database")
        copy("menuflow.database_opts")
        copy("server.hostname")
        copy("server.port")
        copy("server.public_url")
        copy("server.base_path")
        shared_secret = self["server.unshared_secret"]
        if shared_secret is None or shared_secret == "generate":
            base["server.unshared_secret"] = self._new_token()
        else:
            base["server.unshared_secret"] = shared_secret

        copy_dict("menu")
        copy_dict("utils")
