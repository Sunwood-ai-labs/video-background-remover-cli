from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sync_version import normalize_version, sync_version


class NormalizeVersionTests(unittest.TestCase):
    def test_normalizes_tag_prefix(self) -> None:
        self.assertEqual(normalize_version("v1.2.3"), "1.2.3")

    def test_rejects_invalid_version(self) -> None:
        with self.assertRaises(ValueError):
            normalize_version("release-1")


class SyncVersionTests(unittest.TestCase):
    def test_sync_version_updates_all_tracked_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pyproject = root / "pyproject.toml"
            package_init = root / "src" / "video_background_remover_cli" / "__init__.py"
            lockfile = root / "uv.lock"

            package_init.parent.mkdir(parents=True, exist_ok=True)
            pyproject.write_text('[project]\nversion = "0.1.1"\n', encoding="utf-8")
            package_init.write_text(
                'try:\n    __version__ = version("video-background-remover")\n'
                'except PackageNotFoundError:\n    __version__ = "0.1.1"\n',
                encoding="utf-8",
            )
            lockfile.write_text(
                '[[package]]\nname = "video-background-remover"\nversion = "0.1.1"\n',
                encoding="utf-8",
            )

            updated = sync_version("v0.2.0", root=root)

            self.assertEqual(
                {path.relative_to(root).as_posix() for path in updated},
                {
                    "pyproject.toml",
                    "src/video_background_remover_cli/__init__.py",
                    "uv.lock",
                },
            )
            self.assertIn('version = "0.2.0"', pyproject.read_text(encoding="utf-8"))
            self.assertIn('__version__ = "0.2.0"', package_init.read_text(encoding="utf-8"))
            self.assertIn('version = "0.2.0"', lockfile.read_text(encoding="utf-8"))

    def test_sync_version_skips_missing_optional_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pyproject = root / "pyproject.toml"
            package_init = root / "src" / "video_background_remover_cli" / "__init__.py"

            package_init.parent.mkdir(parents=True, exist_ok=True)
            pyproject.write_text('[project]\nversion = "0.1.1"\n', encoding="utf-8")
            package_init.write_text(
                'try:\n    __version__ = version("video-background-remover")\n'
                'except PackageNotFoundError:\n    __version__ = "0.1.1"\n',
                encoding="utf-8",
            )

            updated = sync_version("v0.2.0", root=root)

            self.assertEqual(
                {path.relative_to(root).as_posix() for path in updated},
                {
                    "pyproject.toml",
                    "src/video_background_remover_cli/__init__.py",
                },
            )


if __name__ == "__main__":
    unittest.main()
