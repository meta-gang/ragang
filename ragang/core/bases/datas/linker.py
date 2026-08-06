from dataclasses import dataclass

from ragang.exceptions.user.module import DependencyConnectionException


class Linker:
    def __init__(self, module_id: str):
        self.module_id: str = module_id
        self.dependency_ids: list[str] = []
        self.is_or: bool = False
        self.is_and: bool = False

    def __and__(self, other: 'Linker') -> 'Linker':
        self.__prevent_cross_operator_usage(other, is_or=False)
        self.is_and = True
        self.__add_dependency(other)
        return self

    def __or__(self, other: 'Linker') -> 'Linker':
        self.__prevent_cross_operator_usage(other, is_or=True)
        self.is_or = True
        self.__add_dependency(other)
        return self

    def __add_dependency(self, other: 'Linker') -> None:
        self.dependency_ids.append(other.module_id)
        self.dependency_ids.extend(other.dependency_ids)

    def __prevent_cross_operator_usage(self, other: 'Linker', is_or: bool) -> None:
        # check both operands; python evaluates '&' before '|', so a mixed expression
        # such as 'a | (b & c)' is only detectable from the right operand's state
        for side in (self, other):
            if (side.is_or and not is_or) or (side.is_and and is_or):
                raise DependencyConnectionException("Dependency links must be formed exclusively '&' or '|'")

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
