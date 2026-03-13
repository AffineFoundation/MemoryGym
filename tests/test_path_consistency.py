"""Source-level consistency tests for the 3 evaluation paths.

Ensures bench.py, training/env.py, and eval_task.py (+ inspect_task/tools.py)
stay in sync on critical parameters and patterns. Catches the recurring
"fixed 2 of 3 paths" class of bugs at CI time.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "memorygym"


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text()


# ---------------------------------------------------------------------------
# 1. eval_salt passed to generate_world in all official paths
# ---------------------------------------------------------------------------

class TestEvalSalt:
    """All paths that generate worlds for evaluation must pass eval_salt."""

    def test_bench_passes_eval_salt(self):
        src = _read("bench.py")
        # bench.py uses args.eval_salt — multiline call, use DOTALL
        assert re.search(r"generate_world\(.*?eval_salt", src, re.DOTALL), \
            "bench.py generate_world() missing eval_salt parameter"

    def test_eval_task_passes_eval_salt(self):
        src = _read("worlds/eval_task.py")
        assert re.search(r"generate_world\(.*eval_salt\s*=\s*1", src), \
            "eval_task.py generate_world() missing eval_salt=1"

    def test_sft_trajectory_passes_eval_salt(self):
        src = _read("training/env.py")
        # Find generate_sft_trajectory function and check its generate_world call
        # The function-level call (not the MemoryEnv.reset call) should have eval_salt=1
        fn_match = re.search(
            r"def generate_sft_trajectory.*?(?=\ndef |\nclass |\Z)",
            src, re.DOTALL,
        )
        assert fn_match, "generate_sft_trajectory not found in training/env.py"
        fn_body = fn_match.group()
        assert re.search(r"generate_world\(.*eval_salt\s*=\s*1", fn_body), \
            "generate_sft_trajectory() generate_world() missing eval_salt=1"


# ---------------------------------------------------------------------------
# 2. ChromaDB Edit fallback has old_text guard in all paths
# ---------------------------------------------------------------------------

class TestEditFallbackGuard:
    """ChromaDB Edit fallback must check old_text in result before replacing."""

    _FILES_WITH_EDIT_FALLBACK = [
        "agents/_tool_helpers.py",
        "inspect_task/tools.py",
        "training/env.py",
    ]

    @pytest.mark.parametrize("relpath", _FILES_WITH_EDIT_FALLBACK)
    def test_edit_fallback_checks_old_text(self, relpath: str):
        src = _read(relpath)
        # Every search-based Edit fallback must guard with old_text check
        # Pattern: search(old_text, ...) followed by if ... old_text in results
        if "backend.search(old_text" not in src and \
           "self._backend.search(old_text" not in src:
            pytest.skip(f"{relpath} has no search-based Edit fallback")
        assert "old_text in results[0]" in src, \
            f"{relpath}: Edit fallback missing 'old_text in results[0]' guard"


# ---------------------------------------------------------------------------
# 3. SYSTEM_PROMPT has no strategy leakage
# ---------------------------------------------------------------------------

class TestNoStrategyLeakage:
    """SYSTEM_PROMPT must not contain correction-handling strategy hints."""

    _FORBIDDEN_PATTERNS = [
        r"memory_search the entity",
        r"memory_search\s+\"{entity",
        r"Corrections will arrive",
        r"Handling Corrections",
        r"ACTION REQUIRED.*update.*memory",
        r"Suggestion:\s*store",
        r"Corrections coming",
    ]

    _SYSTEM_PROMPT_FILES = [
        "agents/stream_agent.py",
        "worlds/eval_task.py",
    ]

    @pytest.mark.parametrize("relpath", _SYSTEM_PROMPT_FILES)
    def test_no_strategy_hints_in_system_prompt(self, relpath: str):
        src = _read(relpath)
        # Extract SYSTEM_PROMPT string
        match = re.search(r'SYSTEM_PROMPT\s*=\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')',
                          src, re.DOTALL)
        if not match:
            # Try f-string or regular string
            match = re.search(r'SYSTEM_PROMPT\s*=\s*"(.*?)"', src, re.DOTALL)
        assert match, f"SYSTEM_PROMPT not found in {relpath}"
        prompt_text = match.group(1)

        for pattern in self._FORBIDDEN_PATTERNS:
            assert not re.search(pattern, prompt_text, re.IGNORECASE), \
                f"{relpath} SYSTEM_PROMPT contains forbidden pattern: {pattern}"


# ---------------------------------------------------------------------------
# 4. Edit failure refunds budget in all paths
# ---------------------------------------------------------------------------

class TestEditRefundOnFailure:
    """Edit miss must refund the write budget in all paths."""

    _FILES_WITH_EDIT = [
        "agents/_tool_helpers.py",
        "inspect_task/tools.py",
        "training/env.py",
    ]

    @pytest.mark.parametrize("relpath", _FILES_WITH_EDIT)
    def test_edit_refunds_on_miss(self, relpath: str):
        src = _read(relpath)
        # Must contain budget refund pattern (writes_used -= 1 or max(0, writes_used - 1))
        assert re.search(r"writes?_used\s*(-=\s*1|=\s*max\(0)", src), \
            f"{relpath}: Edit path missing budget refund on failure"


# ---------------------------------------------------------------------------
# 5. RNG seed offsets consistent
# ---------------------------------------------------------------------------

class TestRNGSeeds:
    """Correction and stream RNG use consistent seed offsets across paths."""

    _PATHS_WITH_CORRECTIONS = [
        "bench.py",
        "worlds/eval_task.py",
        "training/env.py",
    ]

    @pytest.mark.parametrize("relpath", _PATHS_WITH_CORRECTIONS)
    def test_correction_rng_seed_offset(self, relpath: str):
        src = _read(relpath)
        # All paths should use seed + 3333 for corrections RNG
        assert re.search(r"seed\s*\+\s*3333", src), \
            f"{relpath}: missing seed+3333 for corrections RNG"


# ---------------------------------------------------------------------------
# 6. Inspect AI tool names use @tool(name=...)
# ---------------------------------------------------------------------------

class TestInspectToolNames:
    """Inspect AI tools must register with OpenClaw-compatible names."""

    _EXPECTED_NAMES = ["Write", "Edit", "Read"]

    def test_tool_decorators_have_correct_names(self):
        src = _read("inspect_task/tools.py")
        for name in self._EXPECTED_NAMES:
            pattern = rf'@tool\(\s*name\s*=\s*"{name}"\s*\)'
            assert re.search(pattern, src), \
                f'inspect_task/tools.py missing @tool(name="{name}")'


# ---------------------------------------------------------------------------
# 7. Default n_entities = 60 across all paths (not 200)
# ---------------------------------------------------------------------------

class TestDefaultEntities:
    """All paths must default to n_entities=60, not the old 200."""

    _PATHS = [
        "worlds/eval_task.py",
        "training/env.py",
    ]

    @pytest.mark.parametrize("relpath", _PATHS)
    def test_default_n_entities_is_60(self, relpath: str):
        src = _read(relpath)
        # Check function signature defaults to 60
        assert re.search(r"n_entities[:\s]*int\s*=\s*60", src), \
            f"{relpath}: n_entities default should be 60"

    @pytest.mark.parametrize("relpath", _PATHS)
    def test_no_hardcoded_200_entities(self, relpath: str):
        src = _read(relpath)
        # Should not have old default of 200 for n_entities
        assert not re.search(r"n_entities\s*=\s*200", src), \
            f"{relpath}: still has old n_entities=200 default"
