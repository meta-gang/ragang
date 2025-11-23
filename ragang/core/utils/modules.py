import importlib
import sys
from pathlib import Path

from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.exceptions.frameworks.general import RagangLoadError
from ragang.exceptions.user.cli import NoEntryPointException, InvalidFlowIdException
from ragang.exceptions.user.structure import RagangStructureException


def load_user_containers(proj_root: str):
    try:
        root = Path(proj_root).resolve()
        sys.path.insert(0, str(root))

        entry_path = Path(proj_root) / 'manager.py'
        if not entry_path.exists():
            raise NoEntryPointException()

        module = importlib.import_module("manager")  # import user_root/manager.py

        if not hasattr(module, "containers"):  # if containers() is not exist in user_root/manager.py
            raise RagangStructureException(f"manager.py must define a 'containers()' function")

        return module.containers
    except Exception as e:
        raise RagangLoadError(f"Failed to load containers() from {proj_root}/manager.py") from e


def create_engine(root_path: str, flow_id: str) -> FlowEngine:
    load_containers = load_user_containers(root_path)  # load entrypoint
    containers = load_containers()
    target_containers = []

    if flow_id is None:
        return FlowEngine(containers)

    for container in containers:
        if container.flow_id == flow_id:
            target_containers.append(container)

    if len(target_containers) == 0:
        raise InvalidFlowIdException(f"Flow id '{flow_id}' is invalid.\n Please choose from flow ids defined in the entrypoint 'manager.py'")


    return FlowEngine(target_containers)