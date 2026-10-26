"""A reused build tree must not mix old dashboard assets into a new wheel."""

from pathlib import Path
import tempfile
import unittest

from build_support import clean_built_dashboard


class BuildSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.source_web = self.project / "ragang/web"
        self.source_web.mkdir(parents=True)
        (self.source_web / "index.html").write_text("current source")
        self.build = self.project / "build/lib"

    def test_only_stale_built_dashboard_is_removed(self):
        web = self.build / "ragang/web"
        web.mkdir(parents=True)
        (web / "old.hash.js").write_text("stale asset")
        (web / "index.html").write_text("old dashboard")
        (self.build / "ragang/core.py").write_text("keep built code")
        templates = self.build / "ragang/templates"
        templates.mkdir()
        (templates / "manager.py").write_text("keep templates")
        other = self.build / "another_package"
        other.mkdir()
        (other / "module.py").write_text("keep other packages")

        self.assertTrue(clean_built_dashboard(self.build, self.project))
        self.assertFalse(web.exists())
        self.assertEqual((self.source_web / "index.html").read_text(), "current source")
        self.assertTrue((self.build / "ragang/core.py").is_file())
        self.assertTrue((templates / "manager.py").is_file())
        self.assertTrue((other / "module.py").is_file())

    def test_missing_build_tree_is_not_created(self):
        self.assertFalse(clean_built_dashboard(self.build, self.project))
        self.assertFalse(self.build.exists())
        self.assertTrue(self.source_web.is_dir())

    def test_source_dashboard_and_its_descendants_are_never_removed(self):
        with self.assertRaisesRegex(ValueError, "overlaps"):
            clean_built_dashboard(self.project, self.project)
        nested_build = self.source_web / "nested-build"
        with self.assertRaisesRegex(ValueError, "overlaps"):
            clean_built_dashboard(nested_build, self.project)
        self.assertEqual((self.source_web / "index.html").read_text(), "current source")

    def test_build_dashboard_containing_source_is_rejected(self):
        target = self.root / "output/ragang/web"
        nested_project = target / "nested-project"
        nested_source = nested_project / "ragang/web"
        nested_source.mkdir(parents=True)
        (nested_source / "index.html").write_text("nested source")
        with self.assertRaisesRegex(ValueError, "overlaps"):
            clean_built_dashboard(self.root / "output", nested_project)
        self.assertEqual((nested_source / "index.html").read_text(), "nested source")

    def test_build_destination_inside_the_source_package_is_rejected(self):
        nested_build = self.project / "ragang" / "nested-build"
        with self.assertRaisesRegex(ValueError, "overlaps"):
            clean_built_dashboard(nested_build, self.project)
        self.assertEqual((self.source_web / "index.html").read_text(), "current source")

    def test_symlinked_package_cannot_clean_the_source(self):
        self.build.mkdir(parents=True)
        try:
            (self.build / "ragang").symlink_to(self.project / "ragang", target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks are unavailable")
        with self.assertRaises(ValueError):
            clean_built_dashboard(self.build, self.project)
        self.assertEqual((self.source_web / "index.html").read_text(), "current source")

    def test_symlinked_dashboard_never_removes_an_unrelated_directory(self):
        (self.build / "ragang").mkdir(parents=True)
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("keep")
        try:
            (self.build / "ragang/web").symlink_to(unrelated, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks are unavailable")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            clean_built_dashboard(self.build, self.project)
        self.assertEqual((unrelated / "keep.txt").read_text(), "keep")

    def test_unexpected_file_is_preserved_instead_of_unlinked(self):
        (self.build / "ragang").mkdir(parents=True)
        target = self.build / "ragang/web"
        target.write_text("unexpected file")
        with self.assertRaisesRegex(ValueError, "directory"):
            clean_built_dashboard(self.build, self.project)
        self.assertEqual(target.read_text(), "unexpected file")
