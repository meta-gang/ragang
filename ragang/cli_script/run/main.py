import json
import os
import time
from argparse import Namespace
from pathlib import Path

from ragang.core.utils.ansi_styler import ANSIStyler
from ragang.core.utils.cli import update_history, read_queries
from ragang.core.utils.modules import create_engine
from ragang.exceptions.user.cli import NotAllowedQueryFileException


def run(args: Namespace):
    flow_id = args.flow_id
    user_root = Path(os.getcwd())
    query_path = user_root / "datas/queries/" / args.query_path
    query_base = (user_root / 'datas/queries').resolve()
    if not query_path.resolve().is_relative_to(query_base):
        raise NotAllowedQueryFileException(args.query_path)

    print(ANSIStyler.style('Running queries...', fore_color='light-cyan', font_style='bold'))

    engine = create_engine(user_root, flow_id)
    q_source = args.query_path.split('/')[0]
    if (q_source, query_path.suffix) not in {('custom', '.txt'), ('generated', '.json')}:
        raise NotAllowedQueryFileException(args.query_path)
    queries = read_queries(query_path, generated=q_source == 'generated')

    print(ANSIStyler.style(f"Running {len(queries)} queries", fore_color='cyan'))
    if not queries:
        raise ValueError("The query file contains no non-empty questions")
    previous = {name: set(cont.storage.results) for name, cont in engine.containers.items()}
    try:
        result = engine.invoke_batch(queries)
    finally:
        if args.save:
            for name, cont in engine.containers.items():
                states = [state for qid, state in cont.storage.results.items() if qid not in previous[name]]
                update_history(name, time.time(), states)
    engine.print_eval()
    failed = sum(bool(state.execution_summary.get('terminated'))
                 for name, cont in engine.containers.items()
                 for qid, state in cont.storage.results.items() if qid not in previous[name])
    if failed:
        location = 'saved history and diagnostics' if args.save else 'printed execution diagnostics (--no-save)'
        raise SystemExit(f"{failed} query execution(s) failed; inspect the {location}")
    return result
