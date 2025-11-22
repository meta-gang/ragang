import argparse
from argparse import Namespace

from .show import run as show_run
from .init import run as init_run
from .gen import run as gen_run
from .run import run as run_run


def main():
    parser = argparse.ArgumentParser(description='RAGANG Framework CLI')
    subparsers = parser.add_subparsers(dest="command", required=True)

    # $ ragang init <path>
    parser_init = subparsers.add_parser("init", help="Initialize a new RAGANG project")
    parser_init.add_argument('path', help="Path to the project directory")
    parser_init.set_defaults(func=init_run)

    # $ ragang show -Q <query_id>
    parser_show = subparsers.add_parser("show", help="Visualize RAGANG project")
    parser_show.add_argument('-F', '--flow', action='store', type=str, help="flow id to run", dest='flow_id', required=True)
    parser_show.set_defaults(func=show_run)

    # $ ragang run
    parser_run = subparsers.add_parser("run", help="Run RAGANG project at cli ")
    parser_run.add_argument('-F', '--flow', action='store', type=str, help="flow id to run", dest='flow_id', required=True)
    parser_run.add_argument('-Q', '--query', action='store', type=str, help="query file path from datas/queries/ to run", dest='query_path', required=True)
    parser_run.add_argument('--no-save', action='store_false', help="don't save the results", dest='x_save', default=True)
    parser_run.set_defaults(func=run_run)

    # $ ragang query-gen
    parser_gen = subparsers.add_parser("query-gen", help="Generate new test queries")
    # document path, query file name to create, inject config
    parser_gen.set_defaults(func=gen_run)

    args: Namespace = parser.parse_args()
    args.func(args)