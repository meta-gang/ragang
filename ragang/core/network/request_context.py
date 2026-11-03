"""Task-local correlation for dashboard requests; CLI engine calls remain independent."""
from contextvars import ContextVar
from dataclasses import dataclass
import re
from uuid import uuid4


@dataclass
class RequestContext:
    request_id: str
    preparation_sent: bool = False


current_request: ContextVar[RequestContext | None] = ContextVar('ragang_dashboard_request', default=None)
EXECUTION_TOPICS = frozenset({'test-query', 'run-rag-file-query', 'run-rag-llm-query'})
EVENT_TOPICS = frozenset({'rag-on', 'module-statu', 'ended-query', 'rag-result-data', 'error'})
_REQUEST_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', re.ASCII)


def validate_request_id(value) -> str:
    if not isinstance(value, str) or _REQUEST_ID.fullmatch(value) is None:
        raise ValueError('request_id는 영문·숫자로 시작하는 1~128자의 영문·숫자·밑줄·하이픈이어야 합니다.')
    return value


def supplied_request_id(message: dict) -> str:
    return validate_request_id(message['request_id']) if 'request_id' in message else str(uuid4())


def correlated_payload(topic: str, payload: dict) -> dict:
    context = current_request.get()
    if topic in EVENT_TOPICS and context is not None:
        return {**payload, 'request_id': context.request_id}
    return payload
