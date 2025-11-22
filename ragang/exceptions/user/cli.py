class NoEntryPointException(Exception):
    def __init__(self):
        super().__init__(
            "Framework Error: 'manager.py' is not found in the root directory. "
            "\nRun 'ragang init <path>' to create a new project.")


class InvalidFlowIdException(Exception):
    pass