import asyncio
import copy
import time
import warnings
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ragang.core.bases.abstracts.base_module import BaseModule
from ragang.core.bases.datas.performance import Performance
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.abstracts.base_container import BaseContainer
from ragang.core.bases.datas.packet import Packet
from ragang.core.bases.datas.state import State
from ragang.core.bases.datas.status import Status
from ragang.core.network.socket_sender import SocketSender
from ragang.core.utils.ansi_styler import ANSIStyler
from ragang.diagnostics import diagnose_state
from ragang.evaluator import attach_evaluator_context, build_run_metadata, safe_failure
from ragang.exceptions.frameworks.engine import FlowExecutionLimitException, FlowIdNotFoundException

from ragang.exceptions.user.module import FlowOutputException, InvalidModuleIdException
from ragang.exceptions.user.module import UnlinkedModuleException, ModuleOutputException
from ragang.exceptions.user.container import DuplicateFlowIdException


class FlowEngine:
    def __init__(self, containers: list[BaseContainer]):
        self.__validate_unique_flow_ids(containers)
        self.containers: dict[str, BaseContainer] = {c.flow_id: c for c in containers}
        self.run_metadata: dict[str, dict] = {
            container.flow_id: build_run_metadata(container) for container in containers
        }
        self.ws_sender: SocketSender = None

    def set_ws_sender(self, ws_sender: SocketSender):
        self.ws_sender = ws_sender

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

        if not isinstance(output, dict) or not all(isinstance(key, str) for key in output):
            raise ModuleOutputException("Module output must be a dictionary with string keys")
        if 'terminal' in output and not isinstance(output['terminal'], bool):
            raise ModuleOutputException("Module output 'terminal' must be a boolean")
        if 'gen' in output and (not isinstance(output['gen'], str) or not output['gen'].strip()):
            raise ModuleOutputException("Module output 'gen' must be a non-empty string")
        if output.get('terminal') is True:
            if 'gen' not in output:
                raise ModuleOutputException("A terminal output requires a non-empty 'gen'")
            if output.get('next'):
                raise ModuleOutputException("A terminal output cannot select successors")
            return {}

        formed_output: dict[str, dict[str, Any]] = {}

        next_module_ids: list[str] = module.direction.get_directions()

        if (dest_mids := output.get('next', None)) is not None:  # conditional branching module
            if not isinstance(dest_mids, list) or not all(isinstance(mid, str) for mid in dest_mids):
                raise ModuleOutputException("Module output 'next' must be a list of module IDs")
            if len(dest_mids) != len(set(dest_mids)):
                raise ModuleOutputException("Module output 'next' must not contain duplicate module IDs")
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

    def __eval(self, c_mid: str, state: State, output: dict[str, Any],
               metrics: list[BaseMetric] | None, parent_execution_ids: list[str] | None = None,
               execution_id: str | None = None) -> list[Performance]:
        if metrics is None:
            return []

        results: list[Performance] = []
        for metric in metrics:
            bindings: dict[str, str] = {}
            try:
                args = [self.__resolve_param(
                    c_mid, state, output, ref, parent_execution_ids, bindings, execution_id
                ) for ref in metric.param_refs]
                performance: Performance = metric.evaluate(*args)
                performance = attach_evaluator_context(
                    performance, metric, parameter_binding_version="ancestry-first-v1"
                )
            except Exception as exc:
                warnings.warn(
                    f"Metric '{metric.__class__.__name__}' was not evaluated: "
                    f"{safe_failure(exc)['type']}: {safe_failure(exc)['message']}",
                    RuntimeWarning,
                )
                performance = attach_evaluator_context(
                    Performance(metric=metric.__class__.__name__, _eval=False),
                    metric,
                    exc,
                    parameter_binding_version="ancestry-first-v1",
                )
            performance.scope["input_execution_ids"] = bindings
            results.append(performance)
        return results

    def __resolve_param(self, c_mid: str, state: State, c_output: dict[str, Any], ref: str,
                        parent_execution_ids: list[str] | None = None,
                        bindings: dict[str, str] | None = None, execution_id: str | None = None):
        module_id, key = ref.split('.', 1)

        # get from current executed module
        if module_id == c_mid:
            if (value := c_output.get(key, None)) is not None:
                if bindings is not None and execution_id:
                    bindings[ref] = execution_id
                return value
            raise ModuleOutputException(f"Cannot resolve metric parameter '{key}' from module '{module_id}' output")

        # get from previously executed other modules
        snapshot: list[Packet] = state.snapshots.get(module_id, None)
        if snapshot is None:
            raise InvalidModuleIdException(module_id=module_id,
                                           additional_msg=f"Cannot resolve metric parameter '{key}' from module '{module_id}' output.\n"
                                                          f"not defined or executed yet")

        # Prefer the execution which actually supplied this queued branch. A
        # deliberately referenced non-ancestor module retains legacy latest-value
        # access, and its exact source execution is recorded in metric scope.
        last_packet = state.get_ancestor_packet(module_id, parent_execution_ids or []) or snapshot[-1]
        if bindings is not None and last_packet.execution_id:
            bindings[ref] = last_packet.execution_id
        output = getattr(last_packet, "data", None)
        value = output.get(key, None)
        if value is None:
            raise ModuleOutputException(f"Cannot resolve metric parameter '{key}' from module '{module_id}' output")

        return value

    async def __run_module(self, cont: BaseContainer, state: State, module: BaseModule,
                           params: dict[str, Any], parent_execution_ids: list[str] | None = None,
                           execution_id: str | None = None) -> Packet:
        # for coroutine-safe module access; allocated here, deallocated after this method returns
        module: BaseModule = copy.deepcopy(module)
        # Modules own their inputs. In-place user transformations must not mutate
        # upstream packets or inputs already queued for a different branch.
        params = copy.deepcopy(params)

        # lazy injection - state obj
        module.lazy_state = state

        # run module
        start_t = time.perf_counter()
        try:
            # may be bounded network io
            if cont.module_timeout_seconds is None:
                output: dict[str, Any] = await module.execute(**params)
            else:
                output = await asyncio.wait_for(
                    module.execute(**params), timeout=cont.module_timeout_seconds
                )
        finally:
            # do not retain a state reference on the copied module, including failure paths
            module.lazy_state = None
        duration = time.perf_counter() - start_t

        # Freeze the returned value before metric evaluation or downstream work.
        # User adapters may reuse mutable buffers between their own calls.
        output = copy.deepcopy(output)

        # validate output
        formed_output: dict[str, dict[str, Any]] = self.__validate_output(cont, module, output)

        # eval performances
        evaluation_started = time.perf_counter()
        performances: list[Performance] = await asyncio.to_thread(
            self.__eval, module.module_id, state, output, module.metrics,
            parent_execution_ids, execution_id
        ) if module.metrics else []
        evaluator_time = time.perf_counter() - evaluation_started if module.metrics else 0.0

        # build packet
        return Packet(src_mid=module.module_id,
                      data=output,
                      formed_output=formed_output,
                      performances=performances,
                      x_time=duration,
                      terminal=output.get('terminal'),
                      evaluator_time=evaluator_time,
                      is_starter=module.is_starter,
                      execution_id=execution_id)

    def __schedule_next_module(self, c_packet: Packet, cont: BaseContainer, status: Status, state: State) -> list[
        tuple[BaseModule, dict[str, Any], list[str]]]:
        scheduled: list[tuple[BaseModule, dict[str, Any], list[str]]] = []
        for n_mid, _ in c_packet.formed_output.items():
            n_module: BaseModule = cont.get_module_by_id(n_mid)
            if status.check_dependencies(n_module.dependency):  # satisfy
                dep_modules: list[str] = n_module.dependency.get_dependencies()
                formed_params: dict[str, Any] = {}
                parent_execution_ids: list[str] = []

                # A retained starter packet and a retry predecessor may both be
                # active in an OR dependency. Assemble oldest to newest so a
                # fresh rewrite wins independently of Linker declaration order.
                # AND joins retain combine-latest semantics: a static predecessor
                # can be reused while another predecessor refreshes its output.
                ordered_dependencies = []
                event_order = {event["execution_id"]: index for index, event in enumerate(state.execution_trace)}
                for dep in dep_modules:
                    if n_module.dependency.is_or and not status.active(dep, n_mid):
                        continue
                    packet = state.get_latest_packet(dep)
                    if packet is None or n_mid not in packet.formed_output:
                        raise ModuleOutputException(
                            f"Active dependency '{dep}' has no selected output for '{n_mid}'"
                        )
                    parent_id = state.latest_execution_id(dep)
                    ordered_dependencies.append((event_order.get(parent_id, -1), dep, packet, parent_id))
                ordered_dependencies.sort(key=lambda item: item[0])
                for _, dep, packet, parent_id in ordered_dependencies:
                    if parent_id:
                        parent_execution_ids.append(parent_id)
                    formed_output = dict(packet.formed_output[n_mid])
                    if duplicated := set(formed_output).intersection(formed_params):
                        warnings.warn(
                            f"Overlapping parameters {duplicated} for module '{n_mid}' are resolved "
                            "using the most recently completed dependency execution.", RuntimeWarning,
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
                scheduled.append((n_module, formed_params, list(dict.fromkeys(parent_execution_ids))))
        return scheduled

    async def __send_module_status(self, module_id: str, is_start: bool, *, state: State,
                                   execution_id: str, status: str) -> None:
        if self.ws_sender:
            await self.ws_sender.send_module_status(
                module_id, is_start, query_id=state.q_id, execution_id=execution_id,
                run_id=state.run_metadata.get("run_id"), status=status,
            )

    def __eval_e2e(self, cont: BaseContainer, query: str, gen: str) -> list[Performance]:
        # Acquiring this lock inside the worker never blocks the event loop.
        with cont._e2e_eval_lock:
            return self.__eval_e2e_unlocked(cont.metrics, query, gen)

    def __eval_e2e_unlocked(self, metrics: list[BaseMetric], query: str, gen: str) -> list[Performance]:
        performances = []
        for metric in metrics:
            try:
                performances.append(attach_evaluator_context(metric.evaluate(query, gen), metric))
            except Exception as exc:
                failure = safe_failure(exc)
                warnings.warn(
                    f"Metric '{metric.__class__.__name__}' was not evaluated: "
                    f"{failure['type']}: {failure['message']}", RuntimeWarning,
                )
                performances.append(attach_evaluator_context(
                    Performance(metric=metric.__class__.__name__, _eval=False), metric, exc,
                ))
        return performances

    @staticmethod
    def __refresh_evaluation_summary(cont: BaseContainer, state: State) -> None:
        module_performances = [
            performance
            for packets in state.snapshots.values()
            for packet in packets
            for performance in packet.performances
        ]
        performances = module_performances + (state.performances or [])
        state.evaluation_summary = {
            "attempted": len(performances),
            "evaluated": sum(performance.did_eval for performance in performances),
            "not_evaluated": sum(not performance.did_eval for performance in performances),
            "configured_e2e_metrics": len(cont.metrics or []),
            "not_reached_e2e_metrics": max(0, len(cont.metrics or []) - len(state.performances or [])),
            # A non-reached module may be an intentionally inactive branch. It is
            # reported separately and is not fabricated as a failed metric attempt.
            "not_reached_modules": [
                {"module_id": mid, "configured_metrics": len(module.metrics or [])}
                for mid, module in cont.modules.items()
                if mid not in state.snapshots and module.metrics
            ],
        }

    async def __execute_flow(self, cont: BaseContainer, q_id: str, query: str,
                             run_context: dict | None = None) -> str:
        status = Status(cont.storage.flow_graph)
        state = State(q_id, query)
        state.run_metadata = copy.deepcopy(self.run_metadata[cont.flow_id])
        state.run_metadata.update(run_context or self.__new_run_context())
        flow_started = time.perf_counter()
        termination_reason = "engine_error"
        success = False
        mod_queue = [(cont.starter, {'query': query}, [])]
        try:
            while mod_queue:
                if len(state.execution_trace) >= cont.max_steps:
                    termination_reason = "max_steps"
                    raise FlowExecutionLimitException(
                        f"Flow '{cont.flow_id}' reached max_steps={cont.max_steps} before producing an answer"
                    )

                c_module, param, parent_execution_ids = mod_queue.pop(0)
                execution_id, execution_index = state.next_execution_identity(c_module.module_id)
                dependency_modules = c_module.dependency.get_dependencies()
                execution_started = time.perf_counter()
                await self.__send_module_status(
                    c_module.module_id, True, state=state, execution_id=execution_id, status="running"
                )
                try:
                    out = await self.__run_module(
                        cont, state, c_module, param, parent_execution_ids, execution_id
                    )
                except BaseException as exc:
                    termination_reason = "cancelled" if isinstance(exc, asyncio.CancelledError) else "module_error"
                    state.record_execution(
                        execution_id=execution_id, module_id=c_module.module_id,
                        execution_index=execution_index, parent_execution_ids=parent_execution_ids,
                        dependency_modules=dependency_modules, status="failed",
                        latency_seconds=time.perf_counter() - execution_started,
                        input_keys=list(param), output_keys=[], next_modules=[], failure=safe_failure(exc),
                    )
                    await self.__send_module_status(
                        c_module.module_id, False, state=state, execution_id=execution_id, status="failed"
                    )
                    raise

                state.save_snapshots(out)
                state.evaluator_latency_seconds += out.evaluator_time
                state.record_execution(
                    execution_id=execution_id, module_id=c_module.module_id,
                    execution_index=execution_index, parent_execution_ids=parent_execution_ids,
                    dependency_modules=dependency_modules, status="completed", latency_seconds=out.x_time,
                    evaluator_latency_seconds=out.evaluator_time, input_keys=list(param),
                    output_keys=list(out.data), next_modules=list(out.formed_output),
                )
                try:
                    status.optimize_n_add_xs(
                        [(c_module.module_id, dst) for dst in out.formed_output],
                        source_mid=c_module.module_id,
                    )
                    if not out.is_answer:
                        mod_queue.extend(self.__schedule_next_module(out, cont, status, state))
                except Exception as exc:
                    termination_reason = "scheduler_error"
                    # The output snapshot survives even if scheduling its successors
                    # fails; annotate this same execution instead of inventing a step.
                    state.execution_trace[-1].update(status="failed", failure=safe_failure(exc))
                    await self.__send_module_status(
                        c_module.module_id, False, state=state, execution_id=execution_id, status="failed"
                    )
                    raise
                await self.__send_module_status(
                    c_module.module_id, False, state=state, execution_id=execution_id, status="completed"
                )
                if out.is_answer:
                    break

            if state.gen is None:
                termination_reason = "missing_output"
                raise FlowOutputException()

            if cont.metrics:
                evaluation_started = time.perf_counter()
                try:
                    state.performances = await asyncio.to_thread(self.__eval_e2e, cont, query, state.gen)
                finally:
                    state.evaluator_latency_seconds += time.perf_counter() - evaluation_started
            termination_reason = "answer"
            success = True
            return state.gen
        except asyncio.CancelledError:
            termination_reason = "cancelled"
            raise
        finally:
            state.total_wall_seconds = time.perf_counter() - flow_started
            state.finalize_execution(termination_reason, success=success)
            self.__refresh_evaluation_summary(cont, state)
            state.diagnosis = diagnose_state(state)
            await cont.save_state(q_id, state)

    @staticmethod
    def __new_run_context() -> dict:
        return {"run_id": str(uuid4()), "started_at": datetime.now(timezone.utc).isoformat()}

    async def __run_query(self, query: str, flow_id: str, run_context: dict | None = None) -> dict:
        q_id = str(uuid4())
        run_context = run_context or self.__new_run_context()
        status = "failed"
        try:
            res = await self.__execute_flow(self.containers[flow_id], q_id, query, run_context)
            status = "completed"
            return {flow_id: {q_id: {'query': query, 'answer': res}}}
        finally:
            if self.ws_sender:
                await self.ws_sender.send_query_end(q_id, run_id=run_context["run_id"], status=status)

    async def __run_container(self, flow_id: str, queries: list[str], run_context: dict | None = None):
        limit = getattr(self.containers[flow_id], "max_concurrency", 8)
        semaphore = asyncio.Semaphore(limit)

        async def bounded_query(query):
            async with semaphore:
                if run_context is None:
                    return await self.__run_query(query, flow_id)
                return await self.__run_query(query, flow_id, run_context)

        tasks = [bounded_query(query) for query in queries]
        # isolate failures: one failing query must not discard the results already produced
        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged = {}
        errors: list[BaseException] = []
        for res in results:
            if isinstance(res, BaseException):
                errors.append(res)
                warnings.warn(f"Skipped a failed execution: {safe_failure(res)['type']}: {safe_failure(res)['message']}", RuntimeWarning)
                continue  # error
            for k, v in res.items():  # merge into {flow_id: {q_id1: {...}, q_id2: {...}, ...}
                merged.setdefault(k, {}).update(v)
        if errors and not merged:
            # nothing survived. a config error fails every query, so report it instead of an empty result
            raise errors[0]
        return merged

    async def async_invoke(self, query: str, flow_ids: list[str] = None):
        run_context = self.__new_run_context()
        async def run():
            tasks = []

            if flow_ids is None:
                f_ids = list(self.containers.keys())
            else:
                # rm undefined container names
                f_ids = self.__validate_flow_ids_existence(flow_ids)

            for f_id in f_ids:
                tasks.append(self.__run_query(query, f_id, run_context))

            if self.ws_sender:
                await self.ws_sender.send_rag_preparation_sig(n_query=1)  # send rag preparation signal

            # isolate failures: one failing query must not discard the results already produced
            results = await asyncio.gather(*tasks, return_exceptions=True)

            merged = {}
            errors: list[BaseException] = []
            for res in results:
                if isinstance(res, BaseException):
                    errors.append(res)
                    warnings.warn(f"Skipped a failed execution: {safe_failure(res)['type']}: {safe_failure(res)['message']}", RuntimeWarning)
                    continue  # error
                for k, v in res.items():
                    merged.setdefault(k, {}).update(v)

            if errors and not merged:
                # nothing survived. a config error fails every query, so report it instead of an empty result
                raise errors[0]

            return merged

        return await run()

    def invoke(self, query: str, flow_ids: list[str] = None):
        return asyncio.run(
            self.async_invoke(query, flow_ids)
        )  # return {flow_id1: {q_id1: {'query': query, 'answer': gen}, q_id2: {...}}, flow_id2: {...}}

    async def async_invoke_batch(self, queries: list[str], flow_ids: list[str] = None):
        run_context = self.__new_run_context()
        async def run():
            tasks = []

            if flow_ids is None:
                f_ids = list(self.containers.keys())
            else:
                # rm undefined container flow ids
                f_ids = self.__validate_flow_ids_existence(flow_ids)

            for f_id in f_ids:
                tasks.append(self.__run_container(f_id, queries, run_context))

            if self.ws_sender:
                await self.ws_sender.send_rag_preparation_sig(len(queries))  # send rag preparation signal

            # isolate failures: one failing query must not discard the results already produced
            results = await asyncio.gather(*tasks, return_exceptions=True)

            merged = {}
            errors: list[BaseException] = []
            for res in results:
                if isinstance(res, BaseException):
                    errors.append(res)
                    warnings.warn(f"Skipped a failed execution: {safe_failure(res)['type']}: {safe_failure(res)['message']}", RuntimeWarning)
                    continue  # error
                for k, v in res.items():
                    merged.setdefault(k, {}).update(v)

            if errors and not merged:
                # nothing survived. a config error fails every query, so report it instead of an empty result
                raise errors[0]

            return merged

        return await run()

    def invoke_batch(self, queries: list[str], flow_ids: list[str] = None):
        return asyncio.run(
            self.async_invoke_batch(queries, flow_ids)
        )  # return {flow_id1: {q_id1: {'query': query, 'answer': gen}, q_id2: {...}}, flow_id2: {...}}

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

    def get_result(self, flow_id: str, q_id: str) -> State:
        cont: BaseContainer = self.containers.get(flow_id, None)
        if cont is None:
            raise FlowIdNotFoundException(f"Flow id: {flow_id} not found in engine")

        return cont.get_result(q_id)
