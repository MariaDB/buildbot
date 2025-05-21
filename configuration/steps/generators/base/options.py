from abc import ABC, abstractmethod
from typing import Union

try:
    # breaking change introduced in python 3.11
    from enum import StrEnum
except ImportError:  # pragma: no cover
    from enum import Enum  # pragma: no cover

    class StrEnum(str, Enum):  # pragma: no cover
        def __str__(self):
            return self.value


class Option(ABC):
    @staticmethod
    def _quote_value(value: str):
        """
        Quote the value if it contains spaces or special characters.
        """
        if " " in value or '"' in value:
            return '"' + value.replace('"', '\\"') + '"'
        return value

    def __init__(self, name: StrEnum, value: Union[str, int, bool] = True):
        assert isinstance(name, StrEnum)
        assert (
            isinstance(value, str) or isinstance(value, bool) or isinstance(value, int)
        )
        self.name = str(name)
        if isinstance(value, str):
            # Quote if necessary.
            self.value = self._quote_value(value)
        else:
            self.value = value

    @abstractmethod
    def as_cmd_arg(self) -> str: ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name}, {self.value})"

    def __str__(self) -> str:
        return self.as_cmd_arg()
