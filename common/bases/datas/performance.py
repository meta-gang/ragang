from common.decorators.serializable import serializable


@serializable
class Performance:
    def __init__(self, score: float = 0, unit: str = '%', metric: str = 'Accuracy', _eval: bool = True):
        self.__score: float = score
        self.__unit: str = unit
        self.__metric: str = metric
        self.__did_eval: bool = _eval

    @property
    def score(self) -> float:
        return self.__score

    @property
    def unit(self) -> str:
        return self.__unit

    def __str__(self):
        # light blue colored score text
        if self.__did_eval:
            return f'{self.__metric}: {self.__score:.2f}{self.__unit}'
        return f"Not evaluated!"
