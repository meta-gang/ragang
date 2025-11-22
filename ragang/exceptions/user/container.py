class DuplicateFlowIdException(ValueError):
    def __init__(self, dup_ids: list[str]):
        super().__init__(f'Duplicate flow ids: {dup_ids}')