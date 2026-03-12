"""Request models for shared background-removal workflows."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field


@dataclass(slots=True)
class ExportRequest:
    """Normalized export request shared by the CLI and WebUI."""

    input_path: str
    output_path: str | None = None
    model_name: str = "isnet-general-use"
    backend_name: str = "rembg"
    use_matanyone_pair: bool = False
    alpha_video_path: str | None = None
    matanyone_root: str | None = None
    matanyone_python: str | None = None
    matanyone_model_name: str = "MatAnyone 2"
    matanyone_device: str = "auto"
    matanyone_performance_profile: str = "auto"
    matanyone_sam_model_type: str = "auto"
    matanyone_cpu_threads: int | None = None
    matanyone_frame_limit: int | None = None
    matanyone_video_target_fps: float = 0.0
    matanyone_output_fps: float | None = None
    matanyone_select_frame: int = 0
    matanyone_end_frame: int | None = None
    positive_points: list[str] = field(default_factory=list)
    negative_points: list[str] = field(default_factory=list)
    fps: int | None = None
    bg_color_text: str | None = None
    bg_image_path: str | None = None
    size_text: str | None = None
    keep_frames: bool = False
    work_dir: str | None = None
    interval_seconds: float | None = None
    output_format: str = "webp"
    animated_format: str | None = None
    animated_fps: int = 10
    max_frames: int | None = None
    no_bg_removal: bool = False
    corner_radius: int = 0

    @classmethod
    def from_namespace(cls, args: Namespace) -> "ExportRequest":
        """Build a request from CLI argparse output."""
        return cls(
            input_path=args.input,
            output_path=args.output,
            model_name=args.model,
            backend_name=args.backend,
            use_matanyone_pair=args.matanyone,
            alpha_video_path=args.alpha_video,
            matanyone_root=args.matanyone_root,
            matanyone_python=args.matanyone_python,
            matanyone_model_name=args.matanyone_model,
            matanyone_device=args.matanyone_device,
            matanyone_performance_profile=args.matanyone_performance_profile,
            matanyone_sam_model_type=args.matanyone_sam_model_type,
            matanyone_cpu_threads=args.matanyone_cpu_threads,
            matanyone_frame_limit=args.matanyone_frame_limit,
            matanyone_video_target_fps=args.matanyone_video_target_fps,
            matanyone_output_fps=args.matanyone_output_fps,
            matanyone_select_frame=args.matanyone_select_frame,
            matanyone_end_frame=args.matanyone_end_frame,
            positive_points=list(args.positive_point),
            negative_points=list(args.negative_point),
            fps=args.fps,
            bg_color_text=args.bg_color,
            bg_image_path=args.bg_image,
            size_text=args.size,
            keep_frames=args.keep_frames,
            work_dir=args.work_dir,
            interval_seconds=args.interval,
            output_format=args.format,
            animated_format=args.animated,
            animated_fps=args.webp_fps,
            max_frames=args.max_frames,
            no_bg_removal=args.no_bg_removal,
            corner_radius=args.corner_radius,
        )
