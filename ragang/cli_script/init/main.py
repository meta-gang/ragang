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

    # Keep derived output and local secrets out of git. Preserve user rules
    # when initializing into an existing directory.
    gitignore = target_path / '.gitignore'
    existing_rules = gitignore.read_text(encoding='utf-8').splitlines() if gitignore.exists() else []
    required_rules = ["__pycache__/", ".env", "history/", "datas/queries/generated/"]
    merged_rules = [*existing_rules]
    for rule in required_rules:
        if rule not in merged_rules:
            merged_rules.append(rule)
    gitignore.write_text("\n".join(merged_rules) + "\n", encoding='utf-8')
