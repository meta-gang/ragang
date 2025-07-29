class MissingMetricDataException(Exception):
    def __init__(self, module_id: str, metric_cls_name: str):
        super().__init__(
            f"Module '{module_id}' uses metric class '{metric_cls_name}' but metric data is not exists in Module output\n"
            f"Please include data for metric with key 'metric'")


class MissingMetricArgumentException(ValueError):
    def __init__(self, cls_name: str, required_params: list[str]):
        super().__init__(f"Missing required datas for '{cls_name}': '{', '.join(required_params)}'")


class ModuleOutputException(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)