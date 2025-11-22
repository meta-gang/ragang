class TemplateNotFoundException(Exception):
    def __init__(self):
        super().__init__("Framework Error: Initial template not found")

class HTMLNotFoundException(Exception):
    def __init__(self):
        super().__init__("Framework Error: Front entrypoint index.html not found")

class RagangInitError(Exception):
    pass