from odin.reporter import Reporter, track
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("odin-monitor")
except PackageNotFoundError:
    try:
        __version__ = version("odin")
    except PackageNotFoundError:
        __version__ = "unknown"

__all__ = ["Reporter", "track", "__version__"]
