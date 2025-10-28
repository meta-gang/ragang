from dataclasses import dataclass

from exceptions.frameworks.modules import DirectionConnectionException


class Linker:
    def __init__(self, module_id: str):
        self.module_id: str = module_id
        self.dependency_ids: list[str] = []
        self.is_or: bool = False

    def __and__(self, other: 'Linker') -> 'Linker':
        Linker.__or__ = Linker.__prevent_cross_operator_usage
        self.__add_dependency(other)
        return self

    def __or__(self, other: 'Linker') -> 'Linker':
        self.is_or = True
        Linker.__and__ = Linker.__prevent_cross_operator_usage
        self.__add_dependency(other)
        return self

    def __add_dependency(self, other: 'Linker') -> None:
        self.dependency_ids.append(other.module_id)
        self.dependency_ids.extend(other.dependency_ids)

    def __prevent_cross_operator_usage(self, other):
        raise DirectionConnectionException("Direction links must be formed exclusively '&' or '|'")

    def build(self, dest_mid: str) -> 'Direction':
        dep_mids = [self.module_id, *self.dependency_ids]
        dependencies: list[tuple[str, str]] = [(src_mid, dest_mid) for src_mid in dep_mids]
        return Dependency(dependencies, self.is_or)


class Direction:
    def __init__(self):
        self.directions: list[tuple[str, str]] = []

    def add_direction(self, direction: list[tuple[str, str]]):
        self.directions.append(direction)

    def get_directions(self) -> list[str]:
        return [d for _, d in self.directions]


@dataclass
class Dependency:
    dependencies: list[tuple[str, str]]
    is_or: bool = False  # means and dep (basically module links are and relation)

    def get_dependencies(self) -> list[str]:
        return [d for d, _ in self.dependencies]


if __name__ == '__main__':
    link: Linker = Linker('m1') | Linker('m2') | Linker('m3')
    dep: Dependency = link.build('m4')
    print(dep)
