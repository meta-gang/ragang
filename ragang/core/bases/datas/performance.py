from ragang.core.decorators.serializable import serializable


@serializable
class Performance:
    def __init__(self, score: float = 0, unit: str = '%', metric: str = 'Accuracy', _eval: bool = True,
                 evaluator: dict | None = None, failure: dict | None = None,
                 evidence: list[dict] | None = None, scope: dict | None = None,
                 direction: str | None = None, metric_version: str | None = None):
        self.__score: float = score
        self.__unit: str = unit
        self.__metric: str = metric
        self.__did_eval: bool = _eval
        self.__evaluator: dict = {} if evaluator is None else evaluator
        self.__failure: dict | None = failure
        self.__evidence: list[dict] = [] if evidence is None else evidence
        self.__scope: dict = {} if scope is None else scope
        self.__direction: str | None = direction
        self.__metric_version: str | None = metric_version

    @property
    def score(self) -> float:
        return self.__score

    @property
    def unit(self) -> str:
        return self.__unit

    @property
    def metric(self) -> str:
        return self.__metric

    @property
    def did_eval(self) -> bool:
        return self.__did_eval

    @property
    def evaluator(self) -> dict:
        return self.__evaluator

    @property
    def failure(self) -> dict | None:
        return self.__failure

    @property
    def evidence(self) -> list[dict]:
        return self.__evidence

    @property
    def scope(self) -> dict:
        return self.__scope

    @property
    def direction(self) -> str | None:
        return self.__direction

    @property
    def metric_version(self) -> str | None:
        return self.__metric_version

    def attach_context(self, evaluator: dict, failure: dict | None = None):
        """Attach safe evaluator provenance after a metric has executed."""
        self.__evaluator = evaluator
        if failure is not None:
            self.__failure = failure

    def __str__(self):
        # light blue colored score text
        if self.__did_eval:
            unit_separator = "" if self.__unit == "%" else " "
            return f'{self.__metric}: {self.__score:.2f}{unit_separator}{self.__unit}'
        return f"{self.__metric}: not evaluated"
