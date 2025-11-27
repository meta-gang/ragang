import json
import os
import time
from argparse import Namespace
from pathlib import Path

from ragang.core.utils.ansi_styler import ANSIStyler
from ragang.core.utils.cli import update_history
from ragang.core.utils.modules import create_engine
from ragang.exceptions.user.cli import NotAllowedQueryFileException


def run(args: Namespace):
    flow_id = args.flow_id
    user_root = Path(os.getcwd())
    query_path = user_root / "datas/queries/" / args.query_path

    print(ANSIStyler.style('Running queries...', fore_color='light-cyan', font_style='bold'))

    engine = create_engine(user_root, flow_id)
    queries = []

    with open(query_path, "r") as f:
        q_source = args.query_path.split('/')[0]
        if q_source == 'custom':
            # custom query files: .txt
            if query_path.suffix != '.txt':
                raise NotAllowedQueryFileException(query_path)
            # load queries
            for line in f:
                queries.append(line.strip())
        elif q_source == 'generated':
            # generated query files: .json
            if query_path.suffix != '.json':
                raise NotAllowedQueryFileException(query_path)
            # load queries
            data = json.load(f)
            query = data['query']
            for q in query:
                queries.append(q['query'])
        else:
            raise NotAllowedQueryFileException(query_path)

    print(ANSIStyler.style(f"Running {len(queries)} queries", fore_color='cyan'))
    res = engine.invoke_batch(queries)
    engine.print_eval()

    if args.x_save:  # without saving results into history
        return

    # add result to history
    for flow_id, tot_res in res.items():
        formed = []
        for q_id in tot_res.keys():
            formed.append(engine.get_result(flow_id, q_id))
        update_history(flow_id, time.time(), formed)