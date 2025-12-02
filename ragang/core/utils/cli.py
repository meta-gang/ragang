import importlib.util
import json
import os
from pathlib import Path
from datetime import datetime

from ragang.core.bases.datas.state import State
from ragang.exceptions.user.cli import NoConfigFileException


def update_history(flow_id: str, ts: float, results: list[State]):
    history_path = Path(os.getcwd()) / 'history' / f"{flow_id}.json"
    history: dict = dict()
    if history_path.exists():
        with open(history_path, 'r', encoding='utf-8') as f:
            history = json.load(f)

    ts_str = datetime.fromtimestamp(ts).strftime("%y%m%d%H%M%S")

    history.setdefault(ts_str, dict())

    for res in results:
        history[ts_str][res.q_id] = res.serialize()

    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)



def get_history(flow_id: str):
    """
    returns contents of flow_id.json
    {
        'ts': {
            'q_id': State,
            'q_id2': State,
            ...
        },
        'ts2': {
            ...
        },
        ...
    }
    """
    history_path = Path(os.getcwd()) / 'history' / f"{flow_id}.json"
    history: dict = dict()
    if history_path.exists():
        with open(history_path, 'r', encoding='utf-8') as f:
            history = json.load(f)

    return history

def load_user_config():
    config_path = Path(os.getcwd()) / 'settings.py'

    if not config_path.exists():
        raise NoConfigFileException()

    spec = importlib.util.spec_from_file_location('user_config', config_path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec from {config_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module