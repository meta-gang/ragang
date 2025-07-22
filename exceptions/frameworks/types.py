class ModuleConnectionException(TypeError):
    def __init__(self, type_name: str):
        super().__init__(f"Cannot connect 'Module class' with type '{type_name}'.\n"
                         f"Please check your '>>' operator")