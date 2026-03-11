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
        "backend": "rembg",
        "matanyone": False,
        "alpha_video": None,
        "matanyone_root": None,
        "matanyone_python": None,
        "matanyone_model": "MatAnyone 2",
        "matanyone_device": "auto",
        "matanyone_performance_profile": "auto",
        "matanyone_sam_model_type": "auto",
        "matanyone_cpu_threads": None,
        "matanyone_frame_limit": None,
        "matanyone_video_target_fps": 0.0,
        "matanyone_output_fps": None,
        "matanyone_select_frame": 0,
        "matanyone_end_frame": None,
        "positive_point": [],
        "negative_point": [],
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
        "no_bg_removal": False,
        "corner_radius": 0,
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


class FakeMatAnyoneRunner:
    instances: list["FakeMatAnyoneRunner"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, str]] = []
        FakeMatAnyoneRunner.instances.append(self)

    def run(self, input_path: str, output_dir: str) -> object:
        self.calls.append((input_path, output_dir))
        return type(
            "FakeRunResult",
            (),
            {
                "output_dir": Path(output_dir),
                "foreground_path": Path(output_dir) / "clip_foreground.mp4",
                "alpha_path": Path(output_dir) / "clip_alpha.mp4",
            },
        )()


class CliRunTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeRemover.instances.clear()
        FakeMatAnyoneRunner.instances.clear()

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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "remove_background": True,
                        "corner_radius": 0,
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
                        "corner_radius": 0,
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
                        "corner_radius": 0,
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
                        "corner_radius": 0,
                    },
                )
            ],
        )

    def test_run_matanyone_backend_processes_regular_video_via_bridge(self) -> None:
        args = build_args(
            input="clips/input.mov",
            output=None,
            backend="matanyone",
            matanyone_root=r"D:\Prj\MatAnyone",
            matanyone_python=r"D:\Prj\MatAnyone\.venv\Scripts\python.exe",
            matanyone_model="MatAnyone 2",
            matanyone_device="cpu",
            positive_point=["320,180"],
            negative_point=["12,12"],
            keep_frames=True,
            fps=24,
            bg_color="white",
            size="300x300",
        )

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch("video_background_remover_cli.cli.MatAnyoneRunner", FakeMatAnyoneRunner),
            patch("video_background_remover_cli.cli.resolve_matanyone_root", return_value=Path(r"D:\Prj\MatAnyone")),
            patch(
                "video_background_remover_cli.cli.resolve_matanyone_python",
                return_value=Path(r"D:\Prj\MatAnyone\.venv\Scripts\python.exe"),
            ),
            patch("video_background_remover_cli.cli._build_run_timestamp", return_value="20260309_010203"),
            patch("video_background_remover_cli.cli.tempfile.mkdtemp", return_value=r"D:\Temp\matanyone_backend_001"),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        runner = FakeMatAnyoneRunner.instances[0]
        self.assertEqual(
            runner.kwargs,
            {
                "repo_root": Path(r"D:\Prj\MatAnyone"),
                "python_executable": Path(r"D:\Prj\MatAnyone\.venv\Scripts\python.exe"),
                "device": "cpu",
                "model_name": "MatAnyone 2",
                "performance_profile": "auto",
                "sam_model_type": "auto",
                "cpu_threads": None,
                "frame_limit": None,
                "video_target_fps": 0.0,
                "output_fps": None,
                "select_frame": 0,
                "end_frame": None,
                "positive_points": ["320,180"],
                "negative_points": ["12,12"],
            },
        )
        self.assertEqual(runner.calls, [("clips/input.mov", r"D:\Temp\matanyone_backend_001")])

        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "process_matanyone_video",
                    {
                        "fg_video_path": r"D:\Temp\matanyone_backend_001\clip_foreground.mp4",
                        "alpha_video_path": r"D:\Temp\matanyone_backend_001\clip_alpha.mp4",
                        "output_path": str(
                            Path("output") / "input_20260309_010203" / "input_bg_removed.mp4"
                        ),
                        "fps": 24,
                        "bg_color": (255, 255, 255),
                        "bg_image_path": None,
                        "keep_frames": True,
                        "work_dir": None,
                        "output_size": (300, 300),
                    },
                )
            ],
        )

    def test_run_matanyone_backend_can_render_animated_output(self) -> None:
        args = build_args(
            input="clips/input.mov",
            output="clip.webp",
            backend="matanyone",
            animated="both",
            matanyone_root=r"D:\Prj\MatAnyone",
            matanyone_python=r"D:\Prj\MatAnyone\.venv\Scripts\python.exe",
        )

        with (
            patch("video_background_remover_cli.bg_remover.VideoBackgroundRemover", FakeRemover),
            patch("video_background_remover_cli.cli.MatAnyoneRunner", FakeMatAnyoneRunner),
            patch("video_background_remover_cli.cli.resolve_matanyone_root", return_value=Path(r"D:\Prj\MatAnyone")),
            patch(
                "video_background_remover_cli.cli.resolve_matanyone_python",
                return_value=Path(r"D:\Prj\MatAnyone\.venv\Scripts\python.exe"),
            ),
        ):
            exit_code = cli.run(args)

        self.assertEqual(exit_code, 0)
        runner_output_dir = Path(FakeMatAnyoneRunner.instances[0].calls[0][1])
        remover = FakeRemover.instances[0]
        self.assertEqual(
            remover.calls,
            [
                (
                    "to_animated_from_mask_pair",
                    {
                        "fg_video_path": str(runner_output_dir / "clip_foreground.mp4"),
                        "alpha_video_path": str(runner_output_dir / "clip_alpha.mp4"),
                        "output_path": "clip.webp",
                        "fps": 10,
                        "max_frames": None,
                        "format": "webp",
                        "output_size": None,
                        "corner_radius": 0,
                    },
                ),
                (
                    "to_animated_from_mask_pair",
                    {
                        "fg_video_path": str(runner_output_dir / "clip_foreground.mp4"),
                        "alpha_video_path": str(runner_output_dir / "clip_alpha.mp4"),
                        "output_path": "clip.gif",
                        "fps": 10,
                        "max_frames": None,
                        "format": "gif",
                        "output_size": None,
                        "corner_radius": 0,
                    },
                ),
            ],
        )

    def test_run_animated_mode_can_skip_background_removal_and_round_corners(self) -> None:
        args = build_args(
            output="clip.webp",
            animated="both",
            no_bg_removal=True,
            corner_radius=24,
        )

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
                        "output_size": None,
                        "remove_background": False,
                        "corner_radius": 24,
                    },
                ),
                (
                    "to_animated",
                    {
                        "video_path": "input.mp4",
                        "output_path": "clip.gif",
                        "fps": 10,
                        "max_frames": None,
                        "format": "gif",
                        "output_size": None,
                        "remove_background": False,
                        "corner_radius": 24,
                    },
                ),
            ],
        )

    def test_run_interval_mode_can_skip_background_removal_and_round_corners(self) -> None:
        args = build_args(
            output="frames",
            interval=1.0,
            format="webp",
            no_bg_removal=True,
            corner_radius=18,
        )

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
                        "output_size": None,
                        "remove_background": False,
                        "corner_radius": 18,
                    },
                )
            ],
        )

    def test_run_rejects_no_bg_removal_without_supported_mode(self) -> None:
        args = build_args(output="result.mp4", no_bg_removal=True)

        with self.assertRaises(ValueError):
            cli.run(args)

    def test_run_rejects_conflicting_matanyone_modes(self) -> None:
        args = build_args(backend="matanyone", matanyone=True)

        with self.assertRaises(ValueError):
            cli.run(args)

    def test_run_rejects_no_bg_removal_with_matanyone_backend(self) -> None:
        args = build_args(backend="matanyone", no_bg_removal=True)

        with self.assertRaises(ValueError):
            cli.run(args)

    def test_main_returns_error_code_on_failure(self) -> None:
        with patch(
            "video_background_remover_cli.cli.run",
            side_effect=RuntimeError("boom"),
        ):
            exit_code = cli.main(["input.mp4", "output.mp4"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
