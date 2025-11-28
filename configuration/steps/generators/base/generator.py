from typing import Iterable

from configuration.steps.generators.base.exceptions import DuplicateFlagException
from configuration.steps.generators.base.options import Option


class BaseGenerator:
    def __init__(
        self,
        base_cmd: list[str],
        flags: Iterable[Option] = [],
        allow_duplicates: bool = False,
    ):
        self.base_cmd = base_cmd
        self.allow_duplicates = allow_duplicates
        self.flags_names: set[str] = set()
        self.flags: list[Option] = []
        self.append_flags(flags)

    def append_flags(self, flags: Iterable[Option]):
        """
        Appends new flags to the generator.

        Raises:
            DuplicateFlagException: If a flag with the same name already
                                    exists and self.allow_duplicates is False.
        """
        for flag in flags:
            # Do not allow duplicate flags being set.
            # Flags should only be set once to avoid confusion about them
            # being overwritten.
            if not self.allow_duplicates and flag.name in self.flags_names:
                # Yes, this is O(N) but this should only happen in cases
                # when we end execution anyway, so a slow error path is ok.
                for other in self.flags:
                    if flag.name == other.name:
                        existing_flag = other
                        break
                raise DuplicateFlagException(flag.name, existing_flag.value, flag.value)
            self.flags_names.add(flag.name)
            self.flags.append(flag)

    def generate(self) -> list[str]:
        """
        Generates the command as a list of strings.
        """
        result = self.base_cmd.copy()
        # arg can be "" for False values in CMakeFlagOption so we skip those
        # flag options don't have a False counterpart nor can be assigned right-hand side values .e.g --trace, --trace-expand
        result += [
            arg
            for flag in sorted(self.flags, key=lambda x: x.name)
            if (arg := flag.as_cmd_arg())
        ]
        return result
