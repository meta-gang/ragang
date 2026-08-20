from ragang.core.bases.datas.linker import Dependency


class Status:
    def __init__(self, flow_graph: list[tuple[str, str]]):
        self.flow_graph: list[tuple[str, str]] = flow_graph
        self.x_status: list[tuple[str, str]] = list()  # execution status (for dependency checking)

    def optimize_n_add_xs(self, cur_x: list[tuple[str, str]]):  # should optimize first and add current x statuses
        # find target tuples to remove in flow graph
        target_links: list[tuple[str, str]] = []

        for _, n_mid in cur_x:
            pending = [n_mid]
            visited: set[str] = set()
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                for link in self.x_status:
                    if link[0] != current:
                        continue
                    target_links.append(link)
                    if link[1] not in visited:
                        pending.append(link[1])

        self.x_status = list(set(self.x_status) - set(target_links))
        # add current execution status
        self.x_status.extend(cur_x)

    def check_dependencies(self, dep: Dependency) -> bool:  # TODO: do we also need to acquire lock here?
        """
        get dep: specific modules' dependency objs
        check whether its dependencies are satisfied
        """
        check = any if dep.is_or else all
        return check(dependency in self.x_status for dependency in dep.dependencies)

    def executed(self, mid: str) -> bool:
        return mid in [src for src, _ in self.x_status]

    def find_loop_before_mid(self, target_mid: str, dept_mids: list[str]) -> str:
        department_ids = set(dept_mids)
        pending = [target_mid]
        visited: set[str] = set()

        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            if current in department_ids:
                return current

            pending.extend(
                destination
                for source, destination in self.flow_graph
                if source == current and destination not in visited
            )
        return None


if __name__ == '__main__':
    flow = [('1', '2'), ('1', '3'), ('2', '4'), ('3', '4'), ('4', '5'), ('4', '6'), ('5', '7'), ('5', '2'), ('6', '7')]
    x_status = [('1', '2'), ('1', '3'), ('2', '4'), ('3', '4'), ('4', '6')]
    status = Status(flow)
    status.x_status = x_status
    print(status.x_status)
    status.optimize_n_add_xs([('6', '7')])
    print(status.x_status)
