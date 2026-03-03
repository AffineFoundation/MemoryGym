"""Scenario generation: domain selection and KB generation."""

from __future__ import annotations

import random

from memorybench.domains import ALL_DOMAINS, Domain


def select_domains(seed: int, n: int = 2) -> list[Domain]:
    """Select n domains deterministically from the global pool.

    Uses rotation (seed % len) to exclude one domain, guaranteeing
    uniform distribution across seeds.  The remaining two are shuffled
    for order randomness.
    """
    excluded_idx = seed % len(ALL_DOMAINS)
    chosen = [d for i, d in enumerate(ALL_DOMAINS) if i != excluded_idx]
    rng = random.Random(seed + 7777)
    rng.shuffle(chosen)
    return chosen[:n]
