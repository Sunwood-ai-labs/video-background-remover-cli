from argparse import Namespace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_background_remover_cli import cli


def build_args(**overrides: object) -> Namespace:
    defaults = {
        "input": "input.mp4",
        "output": "output.mp4",
        "model": "isnet-general-use",
        "matanyone": False,
        "alpha_video": None,
        "fps": None,
        "bg_color": None,
        "bg_image": None,
        "size": None,
        "keep_frames": False,
        "work_dir": None,
        "interval": None,
        "format": "webp",
        "animated": None,
        "webp_fps": 10,
        "max_frames": None,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


class FakeRemover:
    instances: list["FakeRemover"] = []

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls: list[tuple[str, dict[str, object]]] = []
        FakeRemover.instances.append(self)

    def to_animated(self, **kwargs: object) -> None:
        self.calls.append(("to_animated", kwargs))

    def to_animated_from_mask_pair(self, **kwargs: object) -> None:
        self.calls.append(("to_animated_from_mask_pair", kwargs))

    def extract_frames_interval(self, **kwargs: object) -> None:
        self.calls.append(("extract_frames_interval", kwargs))

    def extract_matanyone_frames_interval(self, **kwargs: object) -> None:
        self.calls.append(("extract_matanyone_frames_interval", kwargs))

    def process_video(self, **kwargs: object) -> None:
        self.calls.append(("process_video", kwargs))

    def process_matanyone_video(self, **kwargs: object) -> None:
        self.calls.append(("process_matanyone_video", kwargs))


class CliRunTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeRemover.instances.clear()

    def test_run_process_video_mode(self) -> None:
        args = build_args(
            output="result.mp4",
            bg_color="255,128,0",
            fps=24,
            keep_frames=True,
            work_dir="tmp",
        )

        with patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(remover.model_name, "isnet-general-use")
        self.assertEqual(
            remover.calls,
            [
                (
                    "process_video",
                    {
                        "input_path": "input.mp4",
                        "output_path": "result.mp4",
                        "fps": 24,
                        "bg_color": (255, 128, 0),
                        "bg_image_path": None,
                        "keep_frames": True,
                        "work_dir": "tmp",
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_interval_mode_adds_format_suffix(self) -> None:
        args = build_args(output="frames", interval=1.5, format="png")

        with patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "extract_frames_interval",
                    {
                        "video_path": "input.mp4",
                        "output_dir": "frames_png",
                        "interval_sec": 1.5,
                        "format": "png",
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_interval_mode_defaults_output_directory(self) -> None:
        args = build_args(input="clips/input.mov", output=None, interval=2.0, format="webp")

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch("video_background_remover_cli.cli._build_run_timestamp", return_value="20260309_010203"),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "extract_frames_interval",
                    {
                        "video_path": "clips/input.mov",
                        "output_dir": str(
                            Path("output") / "input_20260309_010203" / "input_frames_webp"
                        ),
                        "interval_sec": 2.0,
                        "format": "webp",
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_process_video_mode_defaults_output_path(self) -> None:
        args = build_args(input="clips/input.mov", output=None)

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch("video_background_remover_cli.cli._build_run_timestamp", return_value="20260309_010203"),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "process_video",
                    {
                        "input_path": "clips/input.mov",
                        "output_path": str(
                            Path("output") / "input_20260309_010203" / "input_bg_removed.mov"
                        ),
                        "fps": None,
                        "bg_color": None,
                        "bg_image_path": None,
                        "keep_frames": False,
                        "work_dir": None,
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_animated_mode_defaults_output_path(self) -> None:
        args = build_args(input="clips/input.mov", output=None, animated="webp")

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch("video_background_remover_cli.cli._build_run_timestamp", return_value="20260309_010203"),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "to_animated",
                    {
                        "video_path": "clips/input.mov",
                        "output_path": str(
                            Path("output") / "input_20260309_010203" / "input_animated.webp"
                        ),
                        "fps": 10,
                        "max_frames": None,
                        "format": "webp",
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_process_video_mode_supports_explicit_mp4_format(self) -> None:
        args = build_args(input="clips/input.mov", output=None, format="mp4")

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch("video_background_remover_cli.cli._build_run_timestamp", return_value="20260309_010203"),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "process_video",
                    {
                        "input_path": "clips/input.mov",
                        "output_path": str(
                            Path("output") / "input_20260309_010203" / "input_bg_removed.mp4"
                        ),
                        "fps": None,
                        "bg_color": None,
                        "bg_image_path": None,
                        "keep_frames": False,
                        "work_dir": None,
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_interval_mode_rejects_mp4_format(self) -> None:
        args = build_args(output=None, interval=1.0, format="mp4")

        with self.assertRaises(ValueError):
            cli.run(args)

    def test_run_process_video_mode_forwards_output_size(self) -> None:
        args = build_args(input="clips/input.mov", output="result.mp4", size="300x300")

        with patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "process_video",
                    {
                        "input_path": "clips/input.mov",
                        "output_path": "result.mp4",
                        "fps": None,
                        "bg_color": None,
                        "bg_image_path": None,
                        "keep_frames": False,
                        "work_dir": None,
                        "output_size": (300, 300),
                    },
                )
            ],
        )

    def test_run_interval_mode_forwards_output_size(self) -> None:
        args = build_args(output="frames", interval=1.0, format="webp", size="300x300")

        with patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "extract_frames_interval",
                    {
                        "video_path": "input.mp4",
                        "output_dir": "frames_webp",
                        "interval_sec": 1.0,
                        "format": "webp",
                        "output_size": (300, 300),
                    },
                )
            ],
        )

    def test_run_animated_mode_forwards_output_size(self) -> None:
        args = build_args(output="clip.webp", animated="webp", size="300x300")

        with patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "to_animated",
                    {
                        "video_path": "input.mp4",
                        "output_path": "clip.webp",
                        "fps": 10,
                        "max_frames": None,
                        "format": "webp",
                        "output_size": (300, 300),
                    },
                )
            ],
        )

    def test_run_animated_both_writes_two_formats(self) -> None:
        args = build_args(output="clip.webp", animated="both", webp_fps=8, max_frames=42)

        with patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "to_animated",
                    {
                        "video_path": "input.mp4",
                        "output_path": "clip.webp",
                        "fps": 8,
                        "max_frames": 42,
                        "format": "webp",
                        "output_size": None,
                    },
                ),
                (
                    "to_animated",
                    {
                        "video_path": "input.mp4",
                        "output_path": "clip.gif",
                        "fps": 8,
                        "max_frames": 42,
                        "format": "gif",
                        "output_size": None,
                    },
                ),
            ],
        )

    def test_run_matanyone_mode_defaults_to_animated_webp(self) -> None:
        args = build_args(input="assets/MatAnyone", output=None, matanyone=True)

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch(
                "video_background_remover_cli.cli.resolve_matanyone_inputs",
                return_value=("assets/MatAnyone/sample_fg.mp4", "assets/MatAnyone/sample_alpha.mp4"),
            ),
            patch("video_background_remover_cli.cli._build_run_timestamp", return_value="20260309_010203"),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "to_animated_from_mask_pair",
                    {
                        "fg_video_path": "assets/MatAnyone/sample_fg.mp4",
                        "alpha_video_path": "assets/MatAnyone/sample_alpha.mp4",
                        "output_path": str(
                            Path("output")
                            / "sample_fg_20260309_010203"
                            / "sample_transparent_animated.webp"
                        ),
                        "fps": 10,
                        "max_frames": None,
                        "format": "webp",
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_matanyone_mp4_mode_uses_flattened_video_processing(self) -> None:
        args = build_args(
            input="assets/MatAnyone",
            output="output/clip.mp4",
            matanyone=True,
            bg_color="white",
        )

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch(
                "video_background_remover_cli.cli.resolve_matanyone_inputs",
                return_value=("assets/MatAnyone/sample_fg.mp4", "assets/MatAnyone/sample_alpha.mp4"),
            ),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "process_matanyone_video",
                    {
                        "fg_video_path": "assets/MatAnyone/sample_fg.mp4",
                        "alpha_video_path": "assets/MatAnyone/sample_alpha.mp4",
                        "output_path": "output/clip.mp4",
                        "fps": None,
                        "bg_color": (255, 255, 255),
                        "bg_image_path": None,
                        "keep_frames": False,
                        "work_dir": None,
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_matanyone_animated_mode_uses_pair_processing(self) -> None:
        args = build_args(
            input="assets/MatAnyone",
            output="output/clip.gif",
            matanyone=True,
            animated="gif",
            webp_fps=12,
            max_frames=32,
        )

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch(
                "video_background_remover_cli.cli.resolve_matanyone_inputs",
                return_value=("assets/MatAnyone/sample_fg.mp4", "assets/MatAnyone/sample_alpha.mp4"),
            ),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "to_animated_from_mask_pair",
                    {
                        "fg_video_path": "assets/MatAnyone/sample_fg.mp4",
                        "alpha_video_path": "assets/MatAnyone/sample_alpha.mp4",
                        "output_path": str(Path("output") / "clip.gif"),
                        "fps": 12,
                        "max_frames": 32,
                        "format": "gif",
                        "output_size": None,
                    },
                )
            ],
        )

    def test_run_matanyone_interval_mode_uses_pair_processing(self) -> None:
        args = build_args(
            input="assets/MatAnyone",
            output="frames",
            matanyone=True,
            interval=0.5,
            format="png",
            size="300x300",
        )

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch(
                "video_background_remover_cli.cli.resolve_matanyone_inputs",
                return_value=("assets/MatAnyone/sample_fg.mp4", "assets/MatAnyone/sample_alpha.mp4"),
            ),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "extract_matanyone_frames_interval",
                    {
                        "fg_video_path": "assets/MatAnyone/sample_fg.mp4",
                        "alpha_video_path": "assets/MatAnyone/sample_alpha.mp4",
                        "output_dir": "frames_png",
                        "interval_sec": 0.5,
                        "format": "png",
                        "output_size": (300, 300),
                    },
                )
            ],
        )

    def test_main_returns_error_code_on_failure(self) -> None:
        with patch(
            "video_background_remover_cli.cli.run",
            side_effect=RuntimeError("boom"),
        ):
            exit_code = cli.main(["input.mp4", "output.mp4"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
