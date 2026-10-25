"""Small, side-effect-free input checks shared by built-in text metrics."""


def valid_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_texts(value, minimum: int = 1) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) >= minimum
            and all(valid_text(item) for item in value))
