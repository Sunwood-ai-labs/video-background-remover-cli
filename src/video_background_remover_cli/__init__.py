from importlib.metadata import PackageNotFoundError, version

from .bg_remover import VideoBackgroundRemover

try:
    __version__ = version("video-background-remover")
except PackageNotFoundError:
    __version__ = "0.3.0"

__all__ = ["VideoBackgroundRemover", "__version__"]
