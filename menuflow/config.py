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
        copy("menuflow.ignore.messages_from")
        copy("menuflow.ignore.invitations_from")
        copy("menuflow.database")
        copy("menuflow.database_opts")
        copy("menuflow.sync.room_event_filter")
        copy("menuflow.timeouts.http_request")
        copy("menuflow.timeouts.middlewares")
        copy("menuflow.typing_notification")
        copy("menuflow.send_events")
        copy("menuflow.load_flow_from")
        copy("menuflow.message_rate_limit")
        copy("menuflow.backup_limit")
        copy("menuflow.webhook_queue.time_to_live")
        copy("menuflow.max_recursion_depth")
        copy_dict("menuflow.regex")
        copy("menuflow.mautrix_state_key")
        copy("server.hostname")
        copy("server.port")
        copy("server.public_url")
        copy("server.base_path")
        copy_dict("events")
        copy_dict("nats")
        copy_dict("logging")
        copy_dict("homeserver")
        copy("menuflow.inactivity_options.recreate_on_startup")
        copy("menuflow.inactivity_options.recreate_on_save_flow")
        shared_secret = self["server.unshared_secret"]
        if shared_secret is None or shared_secret == "generate":
            base["server.unshared_secret"] = self._new_token()
        else:
            base["server.unshared_secret"] = shared_secret
