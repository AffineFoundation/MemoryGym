"""Training module: SFT trajectories, RL environment, and training pipelines.

Backward-compatible re-exports — all existing imports continue to work:
    from memorygym.training import MemoryEnv
    from memorygym.training import generate_sft_trajectory, export_trajectories
"""

from .env import MemoryEnv, generate_sft_trajectory, export_trajectories

__all__ = ["MemoryEnv", "generate_sft_trajectory", "export_trajectories"]
