from typing import Union


class WorkerBase:
    """
    Base class for worker instances in the build system.
    This class provides a structure for worker instances, including their name and properties.
    Attributes:
        name (str): The name of the worker.
        properties (dict[str, Union[str, int, bool]]): A dictionary of properties associated with the worker.
    """

    def __init__(self, name: str, properties: dict[str, Union[str, int, bool]]):
        self.name = name
        self.properties = properties

    def __str__(self):
        return self.name
