import shutil
from argparse import Namespace
from pathlib import Path
import os

from ragang.core.utils.ansi_styler import ANSIStyler
from ragang.exceptions.frameworks.cli import TemplateNotFoundException, RagangInitError


def run(args: Namespace):
    target_path: Path = Path(os.getcwd()) / Path(args.path)
    template_path: Path = Path(__file__).parent.parent.parent / 'templates/init_template'

    print(ANSIStyler.style(f"Initializing RAGANG project in '{target_path}'...",
                           fore_color='light-cyan',
                           font_style='bold'))

    target_path.mkdir(parents=True, exist_ok=True)  # create intermediate dirs too

    if not template_path.exists():
        raise TemplateNotFoundException()

    # copy template to user workspace
    try:
        # will overwrite existing dir or files. So, make sure target directory is clean.
        shutil.copytree(template_path, target_path, dirs_exist_ok=True)
    except Exception as e:
        raise RagangInitError(e)

    # keep derived output out of git. the API key comes from RAGANG_API_KEY, so
    # settings.py itself stays tracked
    gitignore = target_path / '.gitignore'
    if not gitignore.exists():
        gitignore.write_text("__pycache__/\nhistory/\n", encoding='utf-8')