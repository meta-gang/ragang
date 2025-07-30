class DependencyConnectionException(TypeError):
    def __init__(self, msg: str):
        super().__init__(msg)


class DuplicateModuleIdException(ValueError):
    def __init__(self, module_ids: set[str]):
        super().__init__(f"Duplicate module ids '{module_ids}'")


class InvalidModuleIdException(ValueError):
    def __init__(self, module_id: str, additional_msg: str=None):
        super().__init__(f"Invalid module id '{module_id}'.\n" + (additional_msg or ''))


class FlowOutputException(Exception):
    def __init__(self, msg: str = None):
        super().__init__(msg or
                         f"The output module must return an generated string with the key 'gen', but none was given")


class MultipleStarterModuleException(Exception):
    def __init__(self, old_mid: str, new_mid: str):
        super().__init__(f"Cannot set multiple starter Module\n"
                         f"Trying to set '{new_mid}' as a starter module again, but module '{old_mid}' is already set as a starter module.")


class StarterModuleException(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
