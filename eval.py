#!/usr/bin/env python3
"""MemoryBench — Memory Management Evaluation CLI.

Usage:
    python eval.py --seed 0 -v              # Single seed, verbose
    python eval.py --seeds 10 --validate    # 10 seeds with invariant checks
    python eval.py --template company       # Specific template
    python eval.py --seeds 5 -o results.json
"""

import sys

from memorybench.bench import main

if __name__ == "__main__":
    sys.exit(main())
