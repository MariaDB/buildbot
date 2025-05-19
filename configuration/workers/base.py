from typing import Union


class WorkerBase:
    def __init__(self, name: str, properties: dict[str, Union[str, int, bool]]):
        self.name = name
        self.properties = properties

    def __str__(self):
        return self.name
