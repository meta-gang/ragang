class NotCorrectModuleId(Exception):
    def __init__(self, module_id: str):
        super().__init__(f"Module not yet executed '{module_id}'")

class NotCorrectDataKey(Exception):
    def __init__(self, module_id: str, key: str):
        super().__init__(f"No key '{key}' found in output of module '{module_id}'")

