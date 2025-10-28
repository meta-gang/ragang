import asyncio
import time
import warnings
from asyncio.queues import Queue
from typing import Any
from uuid import uuid4

from core.bases.abstracts.base_module import BaseModule
from core.bases.datas.performance import Performance
from core.bases.abstracts.base_metric import BaseMetric
from core.bases.abstracts.base_container import BaseContainer
from core.bases.datas.packet import Packet
from core.bases.datas.state import State
from core.bases.status.status import Status
from core.utils.ansi_styler import ANSIStyler

from exceptions.user.keyname import NotCorrectModuleId, NotCorrectDataKey  # TODO: rename exception classes
from exceptions.frameworks.datas import NoOutputData  # TODO: rename exception classes
from exceptions.user.module import UnlinkedModuleException
from exceptions.user.container import DuplicateFlowIdException


class FlowEngine:
    def __init__(self, containers: list[BaseContainer]):
        self.__validate_flow_id(containers)
        self.container: dict[str, BaseContainer] = {c.flow_id: c for c in containers}

    def __validate_flow_id(self, containers: list[BaseContainer]):
        flow_ids: list[str] = [c.flow_id for c in containers]
        if len(set(flow_ids)) != len(flow_ids):
            for dup_id in set(flow_ids):
                flow_ids.remove(dup_id)
            raise DuplicateFlowIdException(flow_ids)

    def __validate_output(self, cont: BaseContainer, module: BaseModule, output: dict[str, Any]) -> dict[
        str, dict[str, Any]]:
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
                    # prepare existing params only; remained params will be updated at module scheduler logic
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
            performance: Performance = metric.evaluate(
                *args)  # TODO: catch type errors or some other parameter related errors
            results.append(performance)
        return results

    # TODO: refactor
    def __resolve_param(self, c_mid: str, state: State, c_output: dict[str, Any], ref: str):
        module_id, key = ref.split('.', 1)
        if module_id == c_mid:
            if (value := c_output.get(key, None)) is not None:
                return value
            raise NoOutputData(module_id=module_id, output=c_output)

        snapshot: list[Packet] = state.snapshots.get(module_id, None)
        if snapshot is None:
            raise NotCorrectModuleId(module_id=module_id)

        last_packet = snapshot[-1]
        output = getattr(last_packet, "data", None)
        if output is None:
            raise NoOutputData(module_id=module_id, output=output)

        value = output.get(key, None)
        if value is None:
            raise NotCorrectDataKey(module_id=module_id, key=key)

        return value  # TODO: type, # matching

    def __run_module(self, cont: BaseContainer, state: State, module: BaseModule, params: dict[str, Any]) -> Packet:
        # lazy injection - state obj
        module.lazy_state = state

        # run module
        start_t = time.time()
        output: dict[str, Any] = module.execute(**params)
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
                    if n_module.dependency.is_or and not status.executed(
                            dep):  # pass conditionally not executed mid
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

    def execute_flow(self, cont: BaseContainer, q_id: str, query: str) -> str:  # asyncio
        status: Status = Status(cont.storage.flow_graph)
        state: State = State(q_id, query)
        mod_queue: list[tuple[BaseModule, dict[str, Any]]] = [(cont.starter, {'query': query})]
        while len(mod_queue) != 0:
            c_module, param = mod_queue.pop(0)
            out: Packet = self.__run_module(cont, state, c_module, param)

            state.save_snapshots(out)

            # optimize / refresh module execution status (manages each module's dependency)
            status.optimize_n_add_xs([(c_module.module_id, dst) for dst in c_module.direction.get_directions()])

            # exit if it is output
            if out.is_answer:
                break

            # schedule next modules
            mod_queue.extend(self.__schedule_next_module(out, cont, status, state))

        gen: str = state.gen

        # eval e2e metrics
        # parameters for the e2e metrics' evaluate() are limited to 'query' and 'gen'
        if cont.metrics is None:
            performances: list[Performance] = [Performance(_eval=False)]
        else:
            performances: list[Performance] = [m.evaluate(query, gen) for m in cont.metrics]

        state.performances = performances

        self.container[cont.flow_id].storage.results[q_id] = state  # save result

        return gen

    def invoke(self, query: str, cont_name: str = None, q_id: str = str(uuid4())) -> dict[str, dict[str, str]]:
        # {cont: {query: query, gen: answer}, cont2: {query: query, gen: answer}, ...}
        answers: dict[str, dict[str, str]] = {}
        if cont_name is None:
            for c_name, cont in self.container.items():
                answers[c_name] = {'query': query,
                                   'gen': self.execute_flow(cont, q_id, query)}
        else:
            answers[cont_name] = {'query': query,
                                  'gen': self.execute_flow(self.container[cont_name], q_id, query)}
        return answers

    def invoke_batch(self, queries: list[str], cont_name: str = None) -> dict[str, dict[int, str]]:  # threading
        # {cont: {0: {query: query, gen: answer}, 1: ...}, cont2: {...}}
        answers: dict[str, dict[int, str]] = {}
        for query in queries:
            q_id: str = str(uuid4())
            answer = self.invoke(query, cont_name=cont_name, q_id=q_id)
            for cont_name, ans in answer.items():
                if answers.get(cont_name, None) is None:
                    answers[cont_name] = {}
                answers[cont_name][q_id] = ans
        return answers

    def print_eval(self, flow_ids: list[str] = None):
        if flow_ids is None:
            containers: list[BaseContainer] = self.container.values()
        else:
            containers: list[BaseContainer] = []
            for flow_id in flow_ids:
                if (cont := self.container.get(flow_id, None)) is None:
                    warnings.warn(f"Trying to access container '{flow_id}' which is not exist", UserWarning)
                containers.append(cont)

        for cont in containers:
            cont.print_eval()
