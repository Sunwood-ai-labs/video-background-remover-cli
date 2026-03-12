from pathlib import Path
import os
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_background_remover_cli.webui import (
    INTERNAL_LAUNCH_FLAG,
    _build_cli_output_target,
    _parse_points_text,
    build_external_launch_command,
    build_pythonpath,
)


class WebUiCommandTests(unittest.TestCase):
    def test_build_external_launch_command_adds_internal_flag(self) -> None:
        command = build_external_launch_command(
            Path(r"C:\Python310\python.exe"),
            ["--port", "9000"],
        )

        self.assertEqual(
            command,
            [
                r"C:\Python310\python.exe",
                "-m",
                "video_background_remover_cli.webui",
                INTERNAL_LAUNCH_FLAG,
                "--port",
                "9000",
            ],
        )

    def test_build_external_launch_command_filters_existing_internal_flag(self) -> None:
        command = build_external_launch_command(
            "python.exe",
            [INTERNAL_LAUNCH_FLAG, "--debug"],
        )

        self.assertEqual(
            command,
            [
                "python.exe",
                "-m",
                "video_background_remover_cli.webui",
                INTERNAL_LAUNCH_FLAG,
                "--debug",
            ],
        )


class PythonPathTests(unittest.TestCase):
    def test_build_pythonpath_prepends_new_paths(self) -> None:
        value = build_pythonpath("existing", "alpha", Path("beta"))

        self.assertEqual(value, os.pathsep.join(["alpha", "beta", "existing"]))

    def test_build_pythonpath_without_existing_value(self) -> None:
        value = build_pythonpath(None, "alpha")

        self.assertEqual(value, "alpha")


class CliHelperTests(unittest.TestCase):
    def test_parse_points_text_accepts_newline_and_semicolon(self) -> None:
        self.assertEqual(
            _parse_points_text("10,20\n30,40;50,60"),
            ["10,20", "30,40", "50,60"],
        )

    def test_parse_points_text_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValueError):
            _parse_points_text("10")

    def test_build_cli_output_target_for_pair_webm(self) -> None:
        target = _build_cli_output_target(
            Path("output") / "case",
            "clip_fg.mp4",
            "matanyone_pair",
            "video",
            "webp",
            "webp",
            "webm",
        )

        self.assertEqual(target, str(Path("output") / "case" / "clip_output.webm"))


if __name__ == "__main__":
    unittest.main()
