def serializable(cls):
    def __serialize(obj):
        from common.bases.abstracts.base_module import BaseModule

        if hasattr(obj, "serialize"):
            return obj.serialize()
        elif isinstance(obj, BaseModule):
            return obj.module_id
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
