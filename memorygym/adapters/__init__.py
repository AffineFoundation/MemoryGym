"""RL framework adapters for MemoryEnv.

Thin integration layers connecting MemoryEnv to RL training frameworks.
MemoryEnv is framework-agnostic; adapters handle framework-specific APIs.

Supported frameworks:
- verl: AgentLoopBase (multi-turn rollout with response_mask)
- slime: custom generate/reward functions (--custom-generate-function-path)
"""
