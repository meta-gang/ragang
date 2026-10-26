"""Setuptools hook: every wheel receives one complete current dashboard build."""

from pathlib import Path
from runpy import run_path

from setuptools import setup
from setuptools.command.build_py import build_py

clean_built_dashboard = run_path(str(Path(__file__).resolve().with_name("build_support.py")))["clean_built_dashboard"]


class DashboardBuild(build_py):
    def run(self):
        clean_built_dashboard(self.build_lib, Path(__file__).resolve().parent)
        super().run()


setup(cmdclass={"build_py": DashboardBuild})
