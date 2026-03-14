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
    _build_resize_ratio_text,
    _build_cli_output_target,
    _compute_scaled_dimensions,
    _parse_points_text,
    build_external_launch_command,
    build_pythonpath,
)
from video_background_remover_cli.background_removal.examples import (
    build_cli_example_cases,
    build_cli_examples_by_mode,
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

    def test_compute_scaled_dimensions_applies_ratio(self) -> None:
        self.assertEqual(_compute_scaled_dimensions(1920, 1080, 0.5), (960, 540))

    def test_build_resize_ratio_text_reports_scaled_size(self) -> None:
        text = _build_resize_ratio_text(
            {"width": 1280, "height": 720},
            0.5,
        )

        self.assertEqual(
            text,
            "Resize ratio 0.50 -> 640 x 360 (from 1280 x 720)",
        )


class WebUiExampleTests(unittest.TestCase):
    def test_cli_example_cases_point_to_repo_assets(self) -> None:
        examples = build_cli_example_cases(ROOT)

        self.assertTrue(examples)
        for example in examples:
            self.assertTrue(Path(example.manual_input_path).exists(), example.manual_input_path)

    def test_cli_examples_by_mode_match_ui_shapes(self) -> None:
        examples_by_mode = build_cli_examples_by_mode(ROOT)

        self.assertEqual(len(examples_by_mode["regular"][0]), 7)
        self.assertEqual(len(examples_by_mode["matanyone_backend"][0]), 7)
        self.assertEqual(len(examples_by_mode["matanyone_pair"][0]), 9)


if __name__ == "__main__":
    unittest.main()
