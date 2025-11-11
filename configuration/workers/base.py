from typing import Union


class WorkerBase:
    ALLOWED_OS_TYPES = ["debian", "redhat", "macos", "windows", "freebsd", "aix"]
    ALLOWED_ARCHS = ["amd64", "aarch64", "ppc64le", "s390x"]
    """
    Base class for worker instances in the build system.
    This class provides a structure for worker instances, including their name and properties.
    Attributes:
        name (str): The name of the worker.
        properties (dict[str, Union[str, int, bool]]): A dictionary of properties associated with the worker.
    """

    def __init__(
        self,
        name: str,
        properties: dict[str, Union[str, int, bool]],
        os_type: str,
        arch: str,
    ):
        self.name = name
        self.os_type = os_type
        self.properties = properties
        self.arch = arch
        self._raise_for_invalid_os_type()
        self._raise_for_invalid_arch()

    def __str__(self):
        return self.name

    def _raise_for_invalid_os_type(self):
        if self.os_type not in WorkerBase.ALLOWED_OS_TYPES:
            raise ValueError(
                f"Invalid OS type: {self.os_type} for {self.name}. Allowed: {WorkerBase.ALLOWED_OS_TYPES}"
            )

    def _raise_for_invalid_arch(self):
        if self.arch not in WorkerBase.ALLOWED_ARCHS:
            raise ValueError(
                f"Invalid arch: {self.arch} for {self.name}. Allowed: {WorkerBase.ALLOWED_ARCHS}"
            )
