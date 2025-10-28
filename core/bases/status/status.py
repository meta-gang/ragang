from core.bases.datas.linker import Dependency


class Status:
    def __init__(self, flow_graph: list[tuple[str, str]]):
        self.flow_graph: list[tuple[str, str]] = flow_graph
        self.x_status: list[tuple[str, str]] = list()  # execution status (for dependency checking)
        # self.lock: Lock = Lock()

    def optimize_n_add_xs(self, cur_x: list[tuple[str, str]]):  # should optimize first and add current x statuses
        # @use_lock(self.lock)
        def run() -> None:
            # find target tuples to remove in flow graph
            target_links: list[tuple[str, str]] = []

            def find_links(mid: str) -> None:
                for link in self.x_status:
                    if link[0] == mid:
                        target_links.append(link)
                        find_links(link[1])

            for _, n_mid in cur_x:
                find_links(n_mid)

            self.x_status = list(set(self.x_status) - set(target_links))
            # add current execution status
            self.x_status.extend(cur_x)

        run()

    def check_dependencies(self, dep: Dependency) -> bool:  # TODO: do we also need to acquire lock here?
        """
        get dep: specific modules' dependency objs
        check whether its dependencies are satisfied
        """

        # @use_lock(self.lock)
        def run() -> bool:
            check = any if dep.is_or else all
            return check(dependency in self.x_status for dependency in dep.dependencies)

        return run()

    def executed(self, mid: str) -> bool:
        return mid in [src for src, _ in self.x_status]

    def find_loop_before_mid(self, target_mid: str, dept_mids: list[str]) -> str:
        if target_mid in dept_mids:
            return target_mid
        for link in self.flow_graph:
            if link[0] == target_mid:
                return self.find_loop_before_mid(link[1], dept_mids)
        return None


if __name__ == '__main__':
    flow = [('1', '2'), ('1', '3'), ('2', '4'), ('3', '4'), ('4', '5'), ('4', '6'), ('5', '7'), ('5', '2'), ('6', '7')]
    x_status = [('1', '2'), ('1', '3'), ('2', '4'), ('3', '4'), ('4', '6')]
    status = Status()
    status.flow_graph = flow
    status.x_status = x_status
    print(status.x_status)
    # asyncio.run(status.optimize_n_add_xs([('5', '2')]))  # should be awaited
    status.optimize_n_add_xs([('6', '7')])
    print(status.x_status)
