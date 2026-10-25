import importlib.util
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from ragang.core.bases.datas.state import State
from ragang.exceptions.user.cli import NoConfigFileException


def read_queries(path: Path, *, generated: bool = False) -> list[str]:
    """Use the same input contract for CLI and dashboard batch execution."""
    with open(path, encoding='utf-8') as source:
        if generated:
            data = json.load(source)
            if not isinstance(data, dict) or not isinstance(data.get('query'), list):
                raise ValueError("Generated query JSON must contain a 'query' array")
            values = [item.get('query') if isinstance(item, dict) else item for item in data['query']]
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError('Generated queries must be non-empty strings')
            queries = [value.strip() for value in values]
        else:
            queries = [line.strip() for line in source if line.strip()]
    if not queries:
        raise ValueError('The query file contains no non-empty questions')
    return queries


def _history_path(flow_id: str) -> Path:
    if (not isinstance(flow_id, str) or not flow_id.strip() or flow_id in {'.', '..'}
            or any(character in '/\\\x00' or ord(character) < 32 for character in flow_id)):
        raise ValueError("History flow_id must be a safe file name without path separators")
    return Path.cwd() / 'history' / f"{flow_id}.json"


@contextmanager
def _history_lock(path: Path):
    """Serialize writers across processes; the adjacent lock never stores data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix('.lock'), 'a+b') as lock:
        os.chmod(lock.name, 0o600)
        if os.name == 'nt':
            import msvcrt
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def update_history(flow_id: str, ts: float, results: list[State]):
    """Atomically save complete States, grouping calls by engine run_id.

    The timestamp prefix preserves chronological ordering and legacy histories.
    A run UUID prevents independent executions in the same second from merging.
    """
    if not results:
        return None
    path = _history_path(flow_id)
    # Preserve legacy host-local ordering; started_at carries the unambiguous UTC time.
    timestamp = datetime.fromtimestamp(ts).strftime("%y%m%d%H%M%S%f")
    fallback_id = str(uuid4())
    with _history_lock(path):
        history = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(history, dict):
            raise ValueError("History must be a mapping of runs; the existing file was preserved")
        last_key = None
        for state in results:
            payload = state.serialize()
            metadata = payload.get('run_metadata')
            if not isinstance(metadata, dict):
                metadata = payload['run_metadata'] = {}
            run_id = metadata.get('run_id')
            if not isinstance(run_id, str) or not run_id.strip():
                run_id = metadata['run_id'] = fallback_id
            metadata.setdefault('started_at', datetime.fromtimestamp(ts, tz=timezone.utc).isoformat())
            # Repeated delivery of the same engine run updates that run only.
            key = next((key for key, states in history.items()
                        if any((item.get('run_metadata') or {}).get('run_id') == run_id
                               for item in states.values() if isinstance(item, dict))), None)
            key = key or f"{timestamp}-{run_id}"
            history.setdefault(key, {})[state.q_id] = payload
            last_key = key
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix=f'.{flow_id}.', delete=False) as output:
                temporary = output.name
                json.dump(history, output, indent=2, ensure_ascii=False, allow_nan=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return last_key



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
    history_path = _history_path(flow_id)
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
