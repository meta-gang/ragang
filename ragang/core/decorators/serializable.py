def serializable(cls):
    def __serialize(obj):
        from ragang.core.bases.abstracts.base_module import BaseModule

        if hasattr(obj, "serialize"):
            return obj.serialize()
        elif isinstance(obj, BaseModule):
            return obj.to_dict()
        elif isinstance(obj, dict):
            return {k: __serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [__serialize(v) for v in obj]
        else:
            return obj

    def serialize(self):
        fields: dict = self.__dict__
        return {k: __serialize(v) for k, v in fields.items()}

    cls.serialize = serialize

    return cls
