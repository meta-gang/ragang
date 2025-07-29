from dataclasses import dataclass

from exceptions.frameworks.modules import DependencyConnectionException


class Linker:
    def __init__(self, module_id: str):
        self.module_id: str = module_id
        self.dependent_ids: list[str] = []
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
        self.dependent_ids.append(other.module_id)
        self.dependent_ids.extend(other.dependent_ids)

    def __prevent_cross_operator_usage(self, other):
        raise DependencyConnectionException("Dependencies links must be formed exclusively '&' or '|'")

    def build(self, dest_mid: str) -> 'Dependency':
        self.dependent_ids.append(self.module_id)
        dependencies: list[tuple[str, str]] = [(dep, dest_mid) for dep in self.dependent_ids]
        return Dependency(dependencies, self.is_or)


@dataclass
class Dependency:
    dependencies: list[tuple[str, str]]
    is_or: bool

    def check_dependencies(self, status: list[tuple[str, str]]) -> bool:
        if self.is_or:
            check = any
        else:
            check = all
        return check(dependency in status for dependency in self.dependencies)

    def get_dependent_mids(self) -> list[str]:
        return [link[0] for link in self.dependencies]

# if __name__ == '__main__':
#     link: Linker = Linker('m1') & Linker('m2') | Linker('m3')
#     dep: Dependency = link.build('m4')
#     print(dep)
#     print(dep.check_dependencies([('m1', 'm4'), ('m3', 'm4'), ('m2', 'm4')]))
