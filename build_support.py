"""Small, dependency-free safeguards for building the bundled dashboard."""

from pathlib import Path
import shutil


def clean_built_dashboard(build_lib: str | Path, project_root: str | Path) -> bool:
    """Remove only the generated dashboard subtree before setuptools copies it.

    ``build_py`` normally overwrites current assets without removing obsolete
    hashed files. A reused build directory could therefore ship assets absent
    from MANIFEST.in. Never follow a dashboard/package symlink or remove the
    source dashboard, even when a caller supplies an unusual ``--build-lib``.
    """
    build_root = Path(build_lib).resolve()
    package = build_root / "ragang"
    target = package / "web"
    source_package = (Path(project_root).resolve() / "ragang").resolve()
    source = (source_package / "web").resolve()

    # Reject both overlap directions: a target inside the source is source
    # content, and a target containing the source would erase it recursively.
    resolved_target = target.resolve()
    if resolved_target.is_relative_to(source_package) or source.is_relative_to(resolved_target):
        raise ValueError("Refusing to clean a build dashboard that overlaps the source dashboard")
    if package.is_symlink() or target.is_symlink() or not resolved_target.is_relative_to(build_root):
        raise ValueError("Refusing to clean a symlinked build dashboard")
    if not target.exists():
        return False
    if not target.is_dir():
        raise ValueError("The build dashboard path must be a directory")
    shutil.rmtree(target)
    return True
