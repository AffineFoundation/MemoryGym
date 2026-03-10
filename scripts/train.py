#!/usr/bin/env python3
"""Unified training CLI: local or remote, single or multi-GPU.

Launches SFT training locally or on a remote GPU machine via SSH,
with real-time log streaming and GPU resource checking.

Usage:
    # Remote training (streams logs back)
    python scripts/train.py --remote user@host:port \
        --model /path/to/Qwen3-4B --data data/sft_train.jsonl --lora

    # Local training (single GPU)
    python scripts/train.py --model ./Qwen3-4B --data data/sft_train.jsonl --lora

    # Multi-GPU (auto-detect or specify)
    python scripts/train.py --remote user@host:port --gpus 1,2 --model ... --lora

    # Check GPU status only
    python scripts/train.py --remote user@host:port --check-gpu

    # Sync code + train
    python scripts/train.py --remote user@host:port --sync --model ... --lora
"""
from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------

def parse_remote(remote: str) -> tuple[str, int]:
    """Parse 'user@host:port' → (user@host, port)."""
    if ":" in remote:
        host, port_str = remote.rsplit(":", 1)
        return host, int(port_str)
    return remote, 22


def ssh_run(host: str, port: int, cmd: str, *,
            capture: bool = False, timeout: int | None = None
            ) -> subprocess.CompletedProcess | subprocess.Popen:
    """Run a command on remote via SSH."""
    ssh_cmd = ["ssh", "-p", str(port),
               "-o", "StrictHostKeyChecking=no",
               "-o", "ConnectTimeout=10",
               host, cmd]
    if capture:
        return subprocess.run(
            ssh_cmd, capture_output=True, text=True,
            timeout=timeout or 30)
    # Streaming mode
    return subprocess.Popen(
        ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)


def rsync_project(host: str, port: int, remote_dir: str) -> None:
    """Sync project to remote, excluding data/checkpoints."""
    print("Syncing project to remote...")
    subprocess.run([
        "rsync", "-az", "--delete",
        "--exclude", "__pycache__",
        "--exclude", ".git",
        "--exclude", "checkpoints/",
        "--exclude", "data/",
        "--exclude", "*.pyc",
        "--exclude", ".env",
        "-e", f"ssh -p {port}",
        ".", f"{host}:{remote_dir}/",
    ], check=True)
    print("  Sync complete.")


# ---------------------------------------------------------------------------
# GPU management
# ---------------------------------------------------------------------------

@dataclass
class GPUInfo:
    index: int
    name: str
    used_mb: int
    free_mb: int
    total_mb: int
    util_pct: int


def check_gpus(host: str, port: int) -> list[GPUInfo]:
    """Query nvidia-smi on remote, return per-GPU info."""
    result = ssh_run(
        host, port,
        "nvidia-smi --query-gpu=index,name,memory.used,memory.free,"
        "memory.total,utilization.gpu --format=csv,noheader,nounits",
        capture=True, timeout=15)
    if result.returncode != 0:
        print(f"ERROR: nvidia-smi failed: {result.stderr}")
        sys.exit(1)

    gpus = []
    for line in result.stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        gpus.append(GPUInfo(
            index=int(parts[0]),
            name=parts[1],
            used_mb=int(parts[2]),
            free_mb=int(parts[3]),
            total_mb=int(parts[4]),
            util_pct=int(parts[5]),
        ))
    return gpus


def print_gpu_table(gpus: list[GPUInfo], min_free_mb: int = 8000) -> None:
    """Print formatted GPU status table."""
    print(f"\n{'GPU':>4}  {'Name':<22} {'Free':>8} {'Total':>8} {'Util':>5}  Status")
    print("-" * 68)
    for g in gpus:
        status = "AVAILABLE" if g.free_mb >= min_free_mb else "IN USE"
        free_gb = g.free_mb / 1024
        total_gb = g.total_mb / 1024
        mark = "●" if status == "AVAILABLE" else "○"
        print(f"  {g.index:>2}  {g.name:<22} {free_gb:>6.1f}GB {total_gb:>6.1f}GB"
              f"  {g.util_pct:>3}%  {mark} {status}")
    print()


def select_gpus(gpus: list[GPUInfo], requested: str,
                min_free_mb: int = 8000) -> list[int]:
    """Select GPUs to use. 'auto' picks all available."""
    if requested != "auto":
        return [int(x) for x in requested.split(",")]
    return [g.index for g in gpus if g.free_mb >= min_free_mb]


# ---------------------------------------------------------------------------
# Log parsing and progress display
# ---------------------------------------------------------------------------

class TrainLogParser:
    """Parse HF Trainer logs and display formatted progress."""

    LOG_RE = re.compile(
        r"\{'loss': '?([\d.e-]+)'?.*?"
        r"'grad_norm': '?([\d.e-]+)'?.*?"
        r"'learning_rate': '?([\d.e-]+)'?.*?"
        r"'epoch': '?([\d.]+)'?",
    )
    PROGRESS_RE = re.compile(r"(\d+)%\|.*?\| (\d+)/(\d+)")
    SUMMARY_RE = re.compile(r"'train_loss': '?([\d.e-]+)'?")

    def __init__(self, total_epochs: int = 3, verbose: bool = False):
        self.total_epochs = total_epochs
        self.verbose = verbose
        self.metrics: list[dict] = []
        self.last_progress = ""

    def parse_line(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return

        # Training metrics log
        m = self.LOG_RE.search(line)
        if m:
            loss = float(m.group(1))
            grad_norm = float(m.group(2))
            lr = float(m.group(3))
            epoch = float(m.group(4))
            self.metrics.append({
                "loss": loss, "grad_norm": grad_norm,
                "lr": lr, "epoch": epoch,
            })
            print(f"  [Epoch {epoch:.1f}/{self.total_epochs}] "
                  f"loss={loss:.4f}  grad_norm={grad_norm:.4f}  "
                  f"lr={lr:.2e}")
            return

        # Training summary
        m = self.SUMMARY_RE.search(line)
        if m:
            print(f"\n  Train loss: {float(m.group(1)):.4f}")
            return

        # Progress bar (show latest only)
        m = self.PROGRESS_RE.search(line)
        if m:
            pct, step, total = m.group(1), m.group(2), m.group(3)
            progress = f"  [{pct}%] Step {step}/{total}"
            if progress != self.last_progress:
                self.last_progress = progress
                print(f"\r{progress}", end="", flush=True)
            return

        # Important messages
        for keyword in ("Saving", "Done", "ERROR", "CUDA", "OOM",
                        "trainable params", "Loading", "Starting"):
            if keyword in line:
                print(f"  {line}")
                return

        if self.verbose:
            print(f"  {line}")


# ---------------------------------------------------------------------------
# Training launchers
# ---------------------------------------------------------------------------

def build_sft_args(args: argparse.Namespace) -> str:
    """Build CLI args string for sft_train.py from parsed args."""
    parts = [
        f"--model {shlex.quote(args.model)}",
        f"--data {shlex.quote(args.data)}",
        f"--output {shlex.quote(args.output)}",
        f"--epochs {args.epochs}",
        f"--batch-size {args.batch_size}",
        f"--grad-accum {args.grad_accum}",
        f"--lr {args.lr}",
        f"--max-length {args.max_length}",
        f"--lora-rank {args.lora_rank}",
    ]
    if args.lora:
        parts.append("--lora")
    if args.bf16:
        parts.append("--bf16")
    return " ".join(parts)


def launch_remote(args: argparse.Namespace) -> int:
    """Launch training on remote GPU machine."""
    host, port = parse_remote(args.remote)

    # 1. Check GPUs
    print(f"Checking GPUs on {host}...")
    gpus = check_gpus(host, port)
    print_gpu_table(gpus, min_free_mb=args.min_free_mb)

    if args.check_gpu:
        return 0

    available = select_gpus(gpus, args.gpus, min_free_mb=args.min_free_mb)
    if not available:
        print("ERROR: No GPUs with sufficient free memory "
              f"(need {args.min_free_mb}MB)")
        return 1

    total_free = sum(g.free_mb for g in gpus if g.index in available)
    print(f"Selected GPUs: {','.join(str(g) for g in available)} "
          f"({total_free/1024:.1f}GB free)")

    # 2. Sync if requested
    if args.sync:
        rsync_project(host, port, args.remote_dir)

    # 3. Build remote command
    gpu_ids = ",".join(str(g) for g in available)
    sft_args = build_sft_args(args)
    # Use $HOME expansion instead of ~ which may not expand in SSH
    remote_dir = args.remote_dir.replace("~", "$HOME")
    env_vars = (
        f"cd {remote_dir} && "
        f"PYTHONPATH=. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "
        f"CUDA_VISIBLE_DEVICES={gpu_ids} "
    )

    if len(available) > 1:
        cmd = (
            f"{env_vars}"
            f"accelerate launch --num_processes {len(available)} "
            f"scripts/sft_train.py {sft_args}"
        )
    else:
        cmd = f"{env_vars}python3 scripts/sft_train.py {sft_args}"

    # 4. Launch and stream
    print(f"\nLaunching training...")
    print(f"  Remote: {host}:{port}")
    print(f"  GPUs: {gpu_ids}")
    print(f"  Command: ...sft_train.py {sft_args}\n")

    proc = ssh_run(host, port, cmd)
    parser = TrainLogParser(
        total_epochs=args.epochs, verbose=args.verbose)

    try:
        for line in proc.stdout:
            parser.parse_line(line)
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n\nInterrupted. Remote process may still be running.")
        print(f"  To check: ssh -p {port} {host} 'pgrep -f sft_train'")
        print(f"  To kill:  ssh -p {port} {host} 'pkill -f sft_train'")
        return 130

    rc = proc.wait()
    if rc == 0:
        print("\nTraining complete!")
        if parser.metrics:
            first = parser.metrics[0]["loss"]
            last = parser.metrics[-1]["loss"]
            print(f"  Loss: {first:.4f} → {last:.4f}")
    else:
        print(f"\nTraining failed (exit code {rc})")
    return rc


def launch_local(args: argparse.Namespace) -> int:
    """Launch training locally."""
    import shutil

    sft_args = build_sft_args(args)

    # Detect available GPUs
    gpu_ids = args.gpus if args.gpus != "auto" else None
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(__import__("pathlib").Path(__file__).parent.parent)

    if gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = gpu_ids
        n_gpus = len(gpu_ids.split(","))
    else:
        n_gpus = 1

    if n_gpus > 1:
        accelerate = shutil.which("accelerate")
        if not accelerate:
            print("ERROR: accelerate required for multi-GPU. "
                  "Install: pip install accelerate")
            return 1
        cmd = (f"{accelerate} launch --num_processes {n_gpus} "
               f"scripts/sft_train.py {sft_args}")
    else:
        cmd = f"{sys.executable} scripts/sft_train.py {sft_args}"

    print(f"Running: {cmd}\n")
    proc = subprocess.Popen(
        cmd, shell=True, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)

    parser = TrainLogParser(
        total_epochs=args.epochs, verbose=args.verbose)

    try:
        for line in proc.stdout:
            parser.parse_line(line)
    except KeyboardInterrupt:
        proc.terminate()
        return 130

    return proc.wait()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MemoryGym training CLI — local or remote",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Remote training
  %(prog)s --remote user@host:60022 --model /path/to/Qwen3-4B --lora

  # Check remote GPU status
  %(prog)s --remote user@host:60022 --check-gpu

  # Local training
  %(prog)s --model ./Qwen3-4B --data data/sft_train.jsonl --lora

  # Multi-GPU with code sync
  %(prog)s --remote user@host:60022 --gpus 1,2 --sync --model ... --lora
""")

    # Remote options
    remote = parser.add_argument_group("remote execution")
    remote.add_argument("--remote", metavar="USER@HOST:PORT",
                        help="SSH target for remote training")
    remote.add_argument("--remote-dir", default="~/MemoryGym",
                        help="Project dir on remote (default: ~/MemoryGym)")
    remote.add_argument("--sync", action="store_true",
                        help="rsync project to remote before training")
    remote.add_argument("--check-gpu", action="store_true",
                        help="Only show GPU status, don't train")
    remote.add_argument("--gpus", default="auto",
                        help="GPU IDs to use, e.g. '0,1' (default: auto)")
    remote.add_argument("--min-free-mb", type=int, default=8000,
                        help="Minimum free VRAM (MB) to consider GPU available")

    # Training options (mirror sft_train.py)
    train = parser.add_argument_group("training")
    train.add_argument("--model", default="",
                       help="Base model path (local or on remote)")
    train.add_argument("--data", default="data/sft_train.jsonl",
                       help="SFT JSONL data path")
    train.add_argument("--output", default="checkpoints/sft",
                       help="Output directory for checkpoints")
    train.add_argument("--lora", action="store_true",
                       help="Use LoRA fine-tuning")
    train.add_argument("--lora-rank", type=int, default=64,
                       help="LoRA rank (default: 64)")
    train.add_argument("--epochs", type=int, default=3,
                       help="Training epochs (default: 3)")
    train.add_argument("--batch-size", type=int, default=1,
                       help="Per-device batch size")
    train.add_argument("--grad-accum", type=int, default=8,
                       help="Gradient accumulation steps")
    train.add_argument("--lr", type=float, default=2e-5,
                       help="Learning rate")
    train.add_argument("--max-length", type=int, default=4096,
                       help="Max sequence length")
    train.add_argument("--bf16", action="store_true", default=True,
                       help="Use bfloat16 (default: true)")

    # Display
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show all output lines")

    args = parser.parse_args()

    # Validate
    if not args.check_gpu and not args.model:
        parser.error("--model is required (unless using --check-gpu)")

    if args.remote:
        rc = launch_remote(args)
    else:
        rc = launch_local(args)

    sys.exit(rc)


if __name__ == "__main__":
    main()
