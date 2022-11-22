from __future__ import annotations

from typing import Any, Dict, List

from attr import dataclass, ib
from jinja2 import Template
from mautrix.types import Obj, SerializableAttrs

from ..jinja.jinja_template import jj_env
from ..utils.base_logger import BaseLogger


@dataclass
class Node(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    type: str = ib(metadata={"json": "type"})

    user_variables: Dict = {}

    def __getattribute__(self, __name: str) -> Any:
        """If the attribute is a string, list, or dict,
        then return the attribute with the appropriate build function

        Parameters
        ----------
        __name : str
            The name of the attribute being accessed.

        Returns
        -------
            The return value is a new object of the same type as the original object.

        """
        attribute = super().__getattribute__(__name)

        if isinstance(attribute, str):
            return self.build_str(attribute)

        if isinstance(attribute, list):
            return self.build_list(attribute)

        if isinstance(attribute, (dict, Obj)) and __name != "user_variables":
            if isinstance(attribute, Obj):
                return self.build_dict(attribute.__dict__)

            return self.build_dict(attribute)

        return attribute

    def build_str(self, item: Obj) -> Template:
        """It takes a string, and returns a template object

        Parameters
        ----------
        item : str
            str

        Returns
        -------
            A Template object

        """
        if not item:
            return

        return jj_env.from_string(item).render(**self.user_variables.__dict__)

    def build_list(self, data: List) -> List:
        """If the item is a string, build a string.
        If the item is a list, build a list. If the item is a dictionary, build a dictionary

        The function is recursive, meaning that it calls itself.
        This is necessary because the data structure is recursive

        Parameters
        ----------
        data : List
            The data to be parsed.

        Returns
        -------
            A list of strings.

        """
        new_list = []

        for item in data:
            if not item:
                continue

            if isinstance(item, str):
                new_list.append(self.build_str(item))

            elif isinstance(item, list):
                new_list += self.build_list(item)

            elif isinstance(item, (dict, Obj)):
                if isinstance(item, Obj):
                    new_list.append(self.build_dict(item.__dict__))
                else:
                    new_list.append(self.build_dict(item))

            else:
                new_list.append(item)

        return new_list

    def build_dict(self, data: Dict) -> Dict:
        """It takes a dictionary and returns a new dictionary with the same keys and values,
        but with the values converted to the appropriate type.

        Parameters
        ----------
        data : Dict
            The data to be processed.

        Returns
        -------
            A dictionary with the same keys as the input dictionary, but with the values replaced
            by the output of the build_str, build_list, and build_dict functions.

        """
        new_dict = {}

        for k, v in data.items():

            if not v:
                continue

            if isinstance(v, str):
                new_dict[k] = self.build_str(v)

            elif isinstance(v, list):
                new_dict[k] = self.build_list(v)

            elif isinstance(v, (dict, Obj)):
                if isinstance(v, Obj):
                    new_dict[k] = self.build_dict(v.__dict__)
                else:
                    new_dict[k] = self.build_dict(v)

            else:
                new_dict[k] = v

        return new_dict
