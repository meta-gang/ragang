import os
from argparse import Namespace
from pathlib import Path

from ragang.core.utils.ansi_styler import ANSIStyler
from ragang.core.utils.modules import create_engine


def run(args: Namespace):
    flow_id = args.flow_id
    user_root = Path(os.getcwd())
    query_path = user_root / "datas/queries/" / args.query_path

    print(ANSIStyler.style('Running queries...', fore_color='light-cyan', font_style='bold'))

    engine = create_engine(user_root, flow_id)
    queries = []
    with open(query_path, "r") as f:
        for line in f:
            queries.append(line.strip())

    engine.invoke_batch(queries)
    engine.print_eval()

    if args.x_save:  # without saving results into history
        return

    # TODO: add result into history
    pass