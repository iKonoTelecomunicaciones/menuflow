from mautrix.util.logging.color import MAU_COLOR, MXID_COLOR, PREFIX, RESET
from mautrix.util.logging.color import ColorFormatter as BaseColorFormatter

INST_COLOR = PREFIX + "35m"  # magenta
LOADER_COLOR = PREFIX + "36m"  # blue


class ColorFormatter(BaseColorFormatter):
    def _color_name(self, module: str) -> str:
        client = "menuflow.client"
        if module.startswith(client + "."):
            suffix = ""
            if module.endswith(".crypto"):
                suffix = f".{MAU_COLOR}crypto{RESET}"
                module = module[: -len(".crypto")]
            module = module[len(client) + 1 :]
            return f"{MAU_COLOR}{client}{RESET}.{MXID_COLOR}{module}{RESET}{suffix}"
        if module.startswith("menuflow."):
            return f"{MAU_COLOR}{module}{RESET}"
        return super()._color_name(module)
