#!/usr/bin/env python3
"""MemoryBench v3 — Evaluation CLI.

Usage:
    python eval.py                              # 30 seeds, all strategies
    python eval.py --seed 42                    # single seed
    python eval.py --seeds 10 --strategy strategic naive
    python eval.py --validate -o results.json   # validate + save
    python eval.py --show-registry              # domain/config info
"""

import sys

from memorybench.cli import main

if __name__ == "__main__":
    sys.exit(main())
