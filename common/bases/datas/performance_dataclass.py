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
    
    @property
    def metric(self) -> str:
        return self.__metric

    def __str__(self):
        # light blue colored score text
        if self.__did_eval:
            return f'{self.__metric}: {self.__score:.2f}{self.__unit}'
        return f"Not evaluated!"
    
"""
class Performance:
    # 8/7 metric_results: dict = None 생성자 매개변수 추가
    def __init__(self, score: float = 0, unit: str = '%', metric: str = 'Accuracy', _eval: bool = True, metric_results: dict = None):
        self.__score: float = score
        self.__unit: str = unit
        self.__metric: str = metric
        self.__did_eval: bool = _eval

        # 8/7 multi-metric을 위해 추가한 부분
        self.__metric_results: dict = metric_results if metric_results is not None else {}
        
        # metric_results가 있는 경우 첫 번째 metric의 결과를 score로 설정
        if self.__metric_results and self.__score == 0:
            first_result = next(iter(self.__metric_results.values()))
            
            if isinstance(first_result, (int, float)):
                self.__score = float(first_result)
                self.__metric = next(iter(self.__metric_results.keys()))

    @property
    def score(self) -> float:
        return self.__score

    @property
    def unit(self) -> str:
        return self.__unit
    
    @property
    def metric(self) -> str:
        return self.__metric

    # 모든 metric의 결과를 반환하는 method
    @property
    def metric_results(self) -> dict:
        return self.__metric_results

    def __str__(self):
        # light blue colored score text
        if self.__did_eval:
            return f'{self.__metric}: {self.__score:.2f}{self.__unit}'
        
        # 모든 metric 결과를 포함하는 문자열 생성
        if self.__metric_results:
            results = [f'{metric}: {score:.2f}{self.__unit}' for metric, score in self.__metric_results.items()]
            return '\n'.join(results)

        return f"Not evaluated!"
"""