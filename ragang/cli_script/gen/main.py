import os
from argparse import Namespace
from pathlib import Path

from ragang.core.utils.ansi_styler import ANSIStyler
from ragang.core.utils.cli import load_user_config
from ragang.core.utils.query_generator.orchestrator import Orchestrator


def run(args: Namespace):
    USER_CONFIG = load_user_config()
    doc_path = args.doc_path
    output_file = Path(os.getcwd()) / 'datas/queries/generated' / args.query_file

    config_values = {k: v for k, v in vars(USER_CONFIG).items() if k.isupper()}
    print(ANSIStyler.style(f"Generate queries with config\n"
                           f"{config_values}", fore_color='light-cyan', font_style="bold"))
    orchestrator = Orchestrator()
    gen_file_names = orchestrator.generate_queries(doc_path, output_file)
    print(ANSIStyler.style(f"Generated query files: {gen_file_names}", fore_color='yellow'))
