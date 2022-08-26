from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy_dict("whatsapp_bridge")
        helper.copy("ignore")
        helper.copy_dict("menu")
