import asyncio
import copy
import time
import warnings
from typing import Any
from uuid import uuid4

from core.bases.abstracts.base_module import BaseModule
from core.bases.datas.performance import Performance
from core.bases.abstracts.base_metric import BaseMetric
from core.bases.abstracts.base_container import BaseContainer
from core.bases.datas.packet import Packet
from core.bases.datas.state import State
from core.bases.datas.status import Status
from core.utils.ansi_styler import ANSIStyler

from exceptions.user.module import FlowOutputException, InvalidModuleIdException
from exceptions.user.module import UnlinkedModuleException, ModuleOutputException
from exceptions.user.container import DuplicateFlowIdException


class FlowEngine:
    def __init__(self, containers: list[BaseContainer]):
        self.__validate_unique_flow_ids(containers)
        self.containers: dict[str, BaseContainer] = {c.flow_id: c for c in containers}

    def __validate_unique_flow_ids(self, containers: list[BaseContainer]):
        flow_ids: list[str] = [c.flow_id for c in containers]
        if len(set(flow_ids)) != len(flow_ids):
            for dup_id in set(flow_ids):
                flow_ids.remove(dup_id)
            raise DuplicateFlowIdException(flow_ids)

    def __validate_flow_ids_existence(self, flow_ids: list[str]) -> list[str]:
        exist_ids: list[str] = self.containers.keys()
        validated_ids: list[str] = []
        for flow_id in flow_ids:
            if flow_id not in exist_ids:
                warnings.warn(f"Trying to access container '{flow_id}' which is not exist", UserWarning)
                continue
            validated_ids.append(flow_id)
        return validated_ids

    def __validate_output(self, cont: BaseContainer, module: BaseModule, output: dict[str, Any]) \
            -> dict[str, dict[str, Any]]:
        """
        after this method, every formed output will be like below
        {
            "dest_mid1": {},
            "dest_mid2": {},
        }
        """

        def set_formed_output(n_mids: list[str]):
            for n_mid in n_mids:
                # get req param keys for each next module
                req_params: list[str] = cont.get_module_by_id(n_mid).param_keys
                formed_output[n_mid] = {}
                for param in req_params:  # find and set corresponding values from output
                    value = output.get(param, None)
                    # prepare existing params only; remained params will be gathered at module scheduler logic
                    if value is not None:
                        formed_output[n_mid][param] = value

        formed_output: dict[str, dict[str, Any]] = {}

        next_module_ids: list[str] = module.direction.get_directions()

        if (dest_mids := output.get('next', None)) is not None:  # conditional branching module
            if unlinked := set(dest_mids) - set(next_module_ids):
                raise UnlinkedModuleException(module.module_id, unlinked)
            set_formed_output(dest_mids)
        else:
            if len(next_module_ids) > 1:
                warnings.warn(  # TODO: replace it with an exception if needed
                    ANSIStyler.style(f"Module '{module.module_id}' does not specify 'next' modules. "
                                     f"Without explicit 'next' definitions, unintended modules may execute, "
                                     f"potentially causing unexpected runtime errors. "
                                     f"Especially in case of '{module.module_id}' is an conditional branching module. "
                                     f"Define the 'next' modules to ensure predictable execution flow.",
                                     fore_color='red', font_style='bold'),
                    RuntimeWarning
                )
            set_formed_output(next_module_ids)

        return formed_output

    def __eval(self, c_mid: str, state: State, output: dict[str, Any], metrics: list[BaseMetric] | None) -> list[
        Performance]:
        if metrics is None:
            return [Performance(_eval=False)]

        results: list[Performance] = []
        for metric in metrics:
            args: list = [self.__resolve_param(c_mid, state, output, ref) for ref in metric.param_refs]
            performance: Performance = metric.evaluate(*args)
            results.append(performance)
        return results

    def __resolve_param(self, c_mid: str, state: State, c_output: dict[str, Any], ref: str):
        module_id, key = ref.split('.', 1)

        # get from current executed module
        if module_id == c_mid:
            if (value := c_output.get(key, None)) is not None:
                return value
            raise ModuleOutputException(f"Cannot resolve metric parameter '{key}' from module '{module_id}' output")

        # get from previously executed other modules
        snapshot: list[Packet] = state.snapshots.get(module_id, None)
        if snapshot is None:
            raise InvalidModuleIdException(module_id=module_id,
                                           additional_msg=f"Cannot resolve metric parameter '{key}' from module '{module_id}' output.\n"
                                                          f"not defined or executed yet")

        last_packet = snapshot[-1]
        output = getattr(last_packet, "data", None)
        value = output.get(key, None)
        if value is None:
            raise ModuleOutputException(f"Cannot resolve metric parameter '{key}' from module '{module_id}' output")

        return value

    async def __run_module(self, cont: BaseContainer, state: State, module: BaseModule,
                           params: dict[str, Any]) -> Packet:
        # for coroutine-safe module access; allocated here, deallocated after this method returns
        module: BaseModule = copy.deepcopy(module)

        # lazy injection - state obj
        module.lazy_state = state

        # run module
        start_t = time.time()
        # may be bounded network io
        output: dict[str, Any] = await module.execute(**params)
        duration = time.time() - start_t

        # rm state obj from executed module for integrity(idk I just thought it is the right sequence)
        module.lazy_state = None

        # validate output
        formed_output: dict[str, dict[str, Any]] = self.__validate_output(cont, module, output)

        # eval performances
        performances: list[Performance] = self.__eval(module.module_id, state, output, module.metrics)

        # build packet
        return Packet(src_mid=module.module_id,
                      data=output,
                      formed_output=formed_output,
                      performances=performances,
                      x_time=duration)

    def __schedule_next_module(self, c_packet: Packet, cont: BaseContainer, status: Status, state: State) -> list[
        tuple[BaseModule, dict[str, Any]]]:
        scheduled: list[tuple[BaseModule, dict[str, Any]]] = []
        for n_mid, _ in c_packet.formed_output.items():
            n_module: BaseModule = cont.get_module_by_id(n_mid)
            if status.check_dependencies(n_module.dependency):  # satisfy
                dep_modules: list[str] = n_module.dependency.get_dependencies()
                formed_params: dict[str, Any] = {}

                # concatenate formed outputs from dep modules' snapshots for next module's param
                for dep in dep_modules:
                    # ensured not none formed_output due to dependency checking
                    if n_module.dependency.is_or and not status.executed(dep):  # pass conditionally not executed mid
                        continue
                    formed_output: dict[str, Any] = state.get_latest_packet(dep).formed_output[n_mid]
                    if duplicated := set(formed_output.keys()).intersection(formed_params.keys()):
                        loop_end_mid: str = status.find_loop_before_mid(n_mid, dep_modules)
                        if loop_end_mid and loop_end_mid == dep:  # loop - flow came back to n_mid
                            for k in duplicated:  # set latest (right before come back)
                                formed_output[k] = state.get_latest_packet(dep).formed_output[n_mid][k]
                        else:
                            warnings.warn(
                                f"Detected duplicate parameters {duplicated} for module '{n_mid}', derived from dependency modules {dep_modules}. "
                                f"These overlapping parameter names may cause value overwriting and lead to unexpected runtime behavior.",
                                RuntimeWarning
                            )
                    formed_params.update(formed_output)

                # warn if all required params are not exists
                for req_param in n_module.param_keys:
                    if formed_params.get(req_param, None) is None:
                        warnings.warn(
                            f"Missing required parameter '{req_param}' for module '{n_mid}'. "
                            f"This parameter was not found in outputs of preceding modules and may result in unexpected runtime behavior.",
                            RuntimeWarning
                        )

                # add run queue
                scheduled.append((n_module, formed_params))
        return scheduled

    async def __execute_flow(self, cont: BaseContainer, q_id: str, query: str) -> str:
        status: Status = Status(cont.storage.flow_graph)
        state: State = State(q_id, query)
        mod_queue: list[tuple[BaseModule, dict[str, Any]]] = [(cont.starter, {'query': query})]
        while len(mod_queue) != 0:
            c_module, param = mod_queue.pop(0)
            out: Packet = await self.__run_module(cont, state, c_module, param)

            state.save_snapshots(out)

            # optimize / refresh module execution status (manages each module's dependency)
            status.optimize_n_add_xs([(c_module.module_id, dst) for dst in c_module.direction.get_directions()])

            # exit if it is output
            if out.is_answer:
                break

            # schedule next modules
            mod_queue.extend(self.__schedule_next_module(out, cont, status, state))

        if (gen := state.gen) is None:
            raise FlowOutputException()

        # eval e2e metrics
        # parameters for the e2e metrics' evaluate() are limited to 'query' and 'gen'
        if cont.metrics is None:
            performances: list[Performance] = [Performance(_eval=False)]
        else:
            performances: list[Performance] = [m.evaluate(query, gen) for m in cont.metrics]

        state.performances = performances

        await self.containers[cont.flow_id].save_state(q_id, state)  # save result (using lock)
        return gen

    async def __run_query(self, query: str, flow_id: str) -> dict[str, dict[str, dict[str, str]]]:
        q_id: str = str(uuid4())
        res = await self.__execute_flow(self.containers[flow_id], q_id, query)
        return {flow_id: {q_id: {'query': query, 'answer': res}}}

    async def __run_container(self, flow_id: str, queries: list[str]):
        tasks = [
            self.__run_query(query, flow_id)
            for query in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged = {}
        for res in results:
            if isinstance(res, Exception):
                continue  # error
            for k, v in res.items():  # merge into {flow_id: {q_id1: {...}, q_id2: {...}, ...}
                merged.setdefault(k, {}).update(v)
        return merged

    def invoke(self, query: str, flow_ids: list[str] = None):
        async def run():
            tasks = []

            if flow_ids is None:
                f_ids = list(self.containers.keys())
            else:
                # rm undefined container names
                f_ids = self.__validate_flow_ids_existence(flow_ids)

            for f_id in f_ids:
                tasks.append(self.__run_query(query, f_id))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            merged = {}
            for res in results:
                if isinstance(res, Exception):
                    continue  # error
                for k, v in res.items():
                    merged.setdefault(k, {}).update(v)

            return merged

        return asyncio.run(
            run())  # return {flow_id1: {q_id1: {'query': query, 'answer': gen}, q_id2: {...}}, flow_id2: {...}}

    def invoke_batch(self, queries: list[str], flow_ids: list[str] = None):  # threading
        async def run():
            tasks = []

            if flow_ids is None:
                f_ids = list(self.containers.keys())
            else:
                # rm undefined container flow ids
                f_ids = self.__validate_flow_ids_existence(flow_ids)

            for f_id in f_ids:
                tasks.append(self.__run_container(f_id, queries))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            merged = {}
            for res in results:
                if isinstance(res, Exception):
                    continue  # error
                for k, v in res.items():
                    merged.setdefault(k, {}).update(v)

            return merged

        return asyncio.run(
            run())  # return {flow_id1: {q_id1: {'query': query, 'answer': gen}, q_id2: {...}}, flow_id2: {...}}

    def print_eval(self, flow_ids: list[str] = None):
        containers: list[BaseContainer] = []
        if flow_ids is None:
            containers = self.containers.values()
        else:
            flow_ids = self.__validate_flow_ids_existence(flow_ids)
            for flow_id in flow_ids:
                containers.append(self.containers[flow_id])

        for cont in containers:
            cont.print_eval()
