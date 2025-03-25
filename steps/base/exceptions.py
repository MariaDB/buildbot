class DuplicateFlagException(Exception):
    def __init__(self, flag_name: str, existing_value: str, new_value: str):
        super().__init__(
            f"Duplicate flag detected: {flag_name}"
            f"(existing: {existing_value}, new: {new_value})"
        )
        super().__init__(f"Duplicate flag detected: {flag_name}")
