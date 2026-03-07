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
        "fps": None,
        "bg_color": None,
        "bg_image": None,
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

    def extract_frames_interval(self, **kwargs: object) -> None:
        self.calls.append(("extract_frames_interval", kwargs))

    def process_video(self, **kwargs: object) -> None:
        self.calls.append(("process_video", kwargs))


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
                    },
                ),
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
