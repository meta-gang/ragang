import numpy as np

class CosineSimilarity:
    @staticmethod
    def compute(vec1, vec2) -> float:
        """
        두 벡터 간의 cosine similarity를 계산
        :param vec1: 1차원 벡터 (list or np.ndarray)
        :param vec2: 1차원 벡터 (list or np.ndarray)
        :return: cosine similarity 값 (float)
        """
        vec1 = np.asarray(vec1)
        vec2 = np.asarray(vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
