"""MemoryGym OpenEnv entry point.

affinetes auto-discovers this file at the project root.
All logic lives in memorygym.env; this is a thin re-export.
"""

from memorygym.env import Actor  # noqa: F401

__all__ = ["Actor"]
