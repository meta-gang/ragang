class UnlinkedModuleException(Exception):
    def __init__(self, src_mid: str, unlinked: list[str]):
        super().__init__(f"Module '{src_mid}' attempted to call unlinked modules '{unlinked}'."
                         f"Check '{src_mid}.output['next']'")
