class NoEntryPointException(Exception):
    def __init__(self):
        super().__init__(
            "Framework Error: 'manager.py' is not found in the root directory. "
            "\nRun 'ragang init <path>' to create a new project.")


class InvalidFlowIdException(Exception):
    pass


class NoConfigFileException(Exception):
    def __init__(self):
        super().__init__(
            "'settings.py' file is not found in the root directory. "
            "\nAdd 'settings.py' to access configuration variables.")

class NotAllowedQueryFileException(Exception):
    def __init__(self, path: str):
        super().__init__(f"Query file paths must be either 'custom/**/file.txt' or 'generated/**/file.json' but received '{path}'")