"""Reusable WebUI example definitions that also serve as tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CliExampleCase:
    """One CLI-export example shown in the WebUI."""

    source_mode: str
    upload_input_path: str | None
    manual_input_path: str
    upload_alpha_path: str | None
    manual_alpha_path: str
    output_path_text: str
    export_mode: str
    video_format: str
    animated_format: str
    frame_format: str

    def to_ui_values(self) -> list[str | None]:
        """Return the exact list shape expected by gr.Examples."""
        if self.source_mode == "matanyone_pair":
            return [
                self.upload_input_path,
                self.manual_input_path,
                self.upload_alpha_path,
                self.manual_alpha_path,
                self.output_path_text,
                self.export_mode,
                self.video_format,
                self.animated_format,
                self.frame_format,
            ]
        return [
            self.upload_input_path,
            self.manual_input_path,
            self.output_path_text,
            self.export_mode,
            self.video_format,
            self.animated_format,
            self.frame_format,
        ]


def build_cli_example_cases(cwd: Path | None = None) -> list[CliExampleCase]:
    """Return the canonical WebUI CLI-export examples."""
    base_dir = (cwd or Path.cwd()).resolve()
    star_cat_video = str((base_dir / "assets" / "star-cat2.mp4").resolve())
    onizuka_walk_video = str((base_dir / "assets" / "onizuka_walk_motion.mp4").resolve())
    matanyone_dir = str((base_dir / "assets" / "MatAnyone").resolve())

    return [
        CliExampleCase(
            source_mode="regular",
            upload_input_path=None,
            manual_input_path=star_cat_video,
            upload_alpha_path=None,
            manual_alpha_path="",
            output_path_text="",
            export_mode="animated",
            video_format="mp4",
            animated_format="webp",
            frame_format="webp",
        ),
        CliExampleCase(
            source_mode="regular",
            upload_input_path=None,
            manual_input_path=onizuka_walk_video,
            upload_alpha_path=None,
            manual_alpha_path="",
            output_path_text="",
            export_mode="interval",
            video_format="mp4",
            animated_format="webp",
            frame_format="png",
        ),
        CliExampleCase(
            source_mode="matanyone_pair",
            upload_input_path=None,
            manual_input_path=matanyone_dir,
            upload_alpha_path=None,
            manual_alpha_path="",
            output_path_text="",
            export_mode="animated",
            video_format="webm",
            animated_format="both",
            frame_format="webp",
        ),
        CliExampleCase(
            source_mode="matanyone_backend",
            upload_input_path=None,
            manual_input_path=star_cat_video,
            upload_alpha_path=None,
            manual_alpha_path="",
            output_path_text="",
            export_mode="video",
            video_format="mp4",
            animated_format="webp",
            frame_format="webp",
        ),
    ]


def build_cli_examples_by_mode(cwd: Path | None = None) -> dict[str, list[list[str | None]]]:
    """Return example lists grouped by WebUI source mode."""
    examples = build_cli_example_cases(cwd)
    return {
        "regular": [
            example.to_ui_values()
            for example in examples
            if example.source_mode == "regular"
        ],
        "matanyone_backend": [
            example.to_ui_values()
            for example in examples
            if example.source_mode == "matanyone_backend"
        ],
        "matanyone_pair": [
            example.to_ui_values()
            for example in examples
            if example.source_mode == "matanyone_pair"
        ],
    }
