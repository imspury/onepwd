"""onepwd — Pythonic wrapper around the 1Password CLI."""

from onepwd.client import OnePasswordClient
from onepwd.exceptions import OnePasswordError

__version__ = "1.0.1"
__all__ = ["OnePasswordClient", "OnePasswordError", "__version__"]
