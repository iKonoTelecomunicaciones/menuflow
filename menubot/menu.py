from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dataclass_wizard import JSONWizard


@dataclass
class Option(JSONWizard):
    id: str
    text: str

    @property
    def level(self) -> str:
        return str(len(self.id.split("-")))


@dataclass
class Menu(JSONWizard):
    id: str
    description: str
    options: List[Option] = field(default_factory=list)
    menu_message: str = ""

    def build_menu_message(self, level: str = "1"):
        if level == "1" and self.description:
            self.menu_message = self.description + "\n"
        for option in self.options:
            if option.level == level:
                self.menu_message = (
                    self.menu_message
                    + ("\n" if self.menu_message else "")
                    + option.id[-1]
                    + " - "
                    + option.text
                )
