#!/usr/bin/env python3
"""Unified training CLI: local or remote, SFT or GRPO.

Launches training locally or on a remote GPU machine via SSH,
with real-time log streaming and GPU resource checking.

Usage:
    # Remote SFT training
    python scripts/train.py sft --remote $GPU_SSH --sync \
        --model /path/to/Qwen3-4B --lora

    # Remote GRPO training
    python scripts/train.py grpo --remote $GPU_SSH --sync \
        --model /path/to/Qwen3-4B --adapter checkpoints/sft \
        --steps 10 --group-size 4

    # Check GPU status only
    python scripts/train.py status --remote $GPU_SSH

    # Monitor a running job
    python scripts/train.py monitor --remote $GPU_SSH --log /tmp/grpo.log
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


def _load_env() -> None:
    """Load .env from project root into os.environ (simple key=value)."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------

def parse_remote(remote: str) -> tuple[str, int]:
    """Parse remote spec into (user@host, port).

    Accepts formats:
      - user@host:port     → (user@host, port)
      - user@host          → (user@host, 22)
      - ssh user@host -p P → (user@host, P)
    """
    # Handle "ssh user@host -p port" format (from .env)
    if remote.startswith("ssh "):
        parts = remote.split()
        host = parts[1]
        port = 22
        for i, p in enumerate(parts):
            if p == "-p" and i + 1 < len(parts):
                port = int(parts[i + 1])
        return host, port
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


def rsync_project(host: str, port: int, remote_dir: str,
                   include_data: bool = False) -> None:
    """Sync project to remote, excluding heavy dirs."""
    print("Syncing project to remote...")
    excludes = [
        "--exclude", "__pycache__",
        "--exclude", ".git",
        "--exclude", "checkpoints/",
        "--exclude", "runs/",
        "--exclude", "*.pyc",
        "--exclude", ".env",
    ]
    if not include_data:
        excludes += ["--exclude", "data/"]
    subprocess.run([
        "rsync", "-az", "--delete",
        *excludes,
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
    print(f"\n{'GPU':>4}  {'Name':<22} {'Free':>8} {'Total':>8} "
          f"{'Util':>5}  Status")
    print("-" * 68)
    for g in gpus:
        status = "AVAILABLE" if g.free_mb >= min_free_mb else "IN USE"
        free_gb = g.free_mb / 1024
        total_gb = g.total_mb / 1024
        mark = "●" if status == "AVAILABLE" else "○"
        print(f"  {g.index:>2}  {g.name:<22} {free_gb:>6.1f}GB "
              f"{total_gb:>6.1f}GB  {g.util_pct:>3}%  {mark} {status}")
    print()


def select_gpus(gpus: list[GPUInfo], requested: str,
                min_free_mb: int = 8000) -> list[int]:
    """Select GPUs to use. 'auto' picks all available."""
    if requested != "auto":
        return [int(x) for x in requested.split(",")]
    available = [g.index for g in gpus if g.free_mb >= min_free_mb]
    return available


# ---------------------------------------------------------------------------
# Log parsers
# ---------------------------------------------------------------------------

class SFTLogParser:
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

        m = self.SUMMARY_RE.search(line)
        if m:
            print(f"\n  Train loss: {float(m.group(1)):.4f}")
            return

        m = self.PROGRESS_RE.search(line)
        if m:
            pct, step, total = m.group(1), m.group(2), m.group(3)
            progress = f"  [{pct}%] Step {step}/{total}"
            if progress != self.last_progress:
                self.last_progress = progress
                print(f"\r{progress}", end="", flush=True)
            return

        for keyword in ("Saving", "Done", "ERROR", "CUDA", "OOM",
                        "trainable params", "Loading", "Starting"):
            if keyword in line:
                print(f"  {line}")
                return

        if self.verbose:
            print(f"  {line}")


class GRPOLogParser:
    """Parse GRPO training logs and display formatted progress."""

    # Match episode lines like:
    # [1/10] G0S0 movie(s=14592): r=0.120 (...) correct=1/10 writes=10 msgs=25
    EPISODE_RE = re.compile(
        r"\[(\d+)/(\d+)\]\s+G(\d+)S(\d+)\s+(\w+)\(s=(\d+)\):\s+"
        r"r=([\d.]+).*?correct=(\d+)/(\d+)\s+writes=(\d+)\s+msgs=(\d+)"
    )
    # Match step summary lines: "Step 1: loss=0.2815 mean_r=0.388 ..."
    STEP_RE = re.compile(
        r"Step\s+(\d+):\s+loss=(-?[\d.]+)\s+mean_r=([\d.]+)"
    )

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.episodes: list[dict] = []
        self.steps: list[dict] = []
        self.current_step = 0

    def parse_line(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return

        # Episode completion
        m = self.EPISODE_RE.search(line)
        if m:
            ep = {
                "step": int(m.group(1)),
                "total_steps": int(m.group(2)),
                "group": int(m.group(3)),
                "sample": int(m.group(4)),
                "template": m.group(5),
                "seed": int(m.group(6)),
                "reward": float(m.group(7)),
                "correct": int(m.group(8)),
                "total_q": int(m.group(9)),
                "writes": int(m.group(10)),
                "msgs": int(m.group(11)),
            }
            self.episodes.append(ep)
            # Compact display
            print(f"  [{ep['step']}/{ep['total_steps']}] "
                  f"G{ep['group']}S{ep['sample']} "
                  f"{ep['template']:>8}  "
                  f"r={ep['reward']:.3f}  "
                  f"correct={ep['correct']}/{ep['total_q']}  "
                  f"writes={ep['writes']}")
            return

        # Step summary
        m = self.STEP_RE.search(line)
        if m:
            step_info = {
                "step": int(m.group(1)),
                "loss": float(m.group(2)),
                "mean_r": float(m.group(3)),
            }
            self.steps.append(step_info)
            print(f"\n  === Step {step_info['step']} "
                  f"=== loss={step_info['loss']:.4f}  "
                  f"mean_r={step_info['mean_r']:.3f}\n")
            return

        # Rollout/Training phase markers
        if "Rollout phase" in line or "Training phase" in line:
            print(f"\n{line}")
            return

        # Important messages
        for keyword in ("Saving", "Done", "ERROR", "CUDA", "OOM",
                        "trainable params", "Loading", "GRPO Training",
                        "Steps:", "Group size", "Output:", "checkpoint"):
            if keyword in line:
                print(f"  {line}")
                return

        if self.verbose:
            print(f"  {line}")

    def summary(self) -> None:
        """Print end-of-training summary."""
        if not self.episodes:
            return
        rewards = [e["reward"] for e in self.episodes]
        correct = [e["correct"] for e in self.episodes]
        total_q = self.episodes[0]["total_q"] if self.episodes else 10
        print(f"\n{'=' * 60}")
        print("GRPO Training Summary")
        print(f"  Episodes: {len(self.episodes)}")
        print(f"  Reward: {min(rewards):.3f} → {max(rewards):.3f} "
              f"(mean={sum(rewards)/len(rewards):.3f})")
        print(f"  Correct: {min(correct)}/{total_q} → "
              f"{max(correct)}/{total_q} "
              f"(mean={sum(correct)/len(correct):.1f})")
        if self.steps:
            losses = [s["loss"] for s in self.steps]
            print(f"  Loss: {losses[0]:.4f} → {losses[-1]:.4f}")
        print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Training launchers
# ---------------------------------------------------------------------------

def build_env_prefix(remote_dir: str, gpu_ids: str) -> str:
    """Build environment variable prefix for remote commands."""
    remote_dir = remote_dir.replace("~", "$HOME")
    return (
        f"cd {remote_dir} && "
        f"PATH=$HOME/.local/bin:$PATH "
        f"PYTHONPATH=. "
        f"PYTHONUNBUFFERED=1 "
        f"HF_HUB_OFFLINE=1 "
        f"TRANSFORMERS_OFFLINE=1 "
        f"PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "
        f"CUDA_VISIBLE_DEVICES={gpu_ids} "
    )


def build_sft_cmd(args: argparse.Namespace) -> str:
    """Build CLI args string for sft_train.py."""
    parts = [
        f"--model {shlex.quote(args.model)}",
        f"--output {shlex.quote(args.output)}",
        f"--epochs {args.epochs}",
        f"--batch-size {args.batch_size}",
        f"--grad-accum {args.grad_accum}",
        f"--lr {args.lr}",
        f"--max-length {args.max_length}",
        f"--lora-rank {args.lora_rank}",
    ]
    if args.data:
        parts.append(f"--data {shlex.quote(args.data)}")
    if args.lora:
        parts.append("--lora")
    if args.bf16:
        parts.append("--bf16")
    return "python3 scripts/sft_train.py " + " ".join(parts)


def build_grpo_cmd(args: argparse.Namespace) -> str:
    """Build CLI args string for grpo_train.py."""
    parts = [
        f"--model {shlex.quote(args.model)}",
        f"--output {shlex.quote(args.output)}",
        f"--steps {args.steps}",
        f"--group-size {args.group_size}",
        f"--groups-per-step {args.groups_per_step}",
        f"--max-turns {args.max_turns}",
        f"--max-new-tokens {args.max_new_tokens}",
        f"--max-length {args.max_length}",
        f"--lr {args.lr}",
        f"--tier {args.tier}",
        f"--lora-rank {args.lora_rank}",
        f"--kl-coeff {args.kl_coeff}",
    ]
    if args.adapter:
        parts.append(f"--adapter {shlex.quote(args.adapter)}")
    if args.templates:
        parts.append(f"--templates {' '.join(args.templates)}")
    if args.ips:
        parts.append("--ips")
    return "python3 scripts/grpo_train.py " + " ".join(parts)


def launch_local_training(args: argparse.Namespace, mode: str) -> int:
    """Launch training locally (when running on GPU machine directly)."""
    import os
    import shutil

    if mode == "sft":
        train_cmd = build_sft_cmd(args)
        parser = SFTLogParser(
            total_epochs=args.epochs, verbose=args.verbose)
    else:
        train_cmd = build_grpo_cmd(args)
        parser = GRPOLogParser(verbose=args.verbose)

    # Set up environment
    env = dict(**os.environ)
    env["PYTHONPATH"] = "."
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    gpu_ids = args.gpus if args.gpus != "auto" else None
    if gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = gpu_ids

    print(f"\nLaunching {mode.upper()} training (local)...")
    print(f"  GPUs: {gpu_ids or 'auto'}")
    print(f"  Command: {train_cmd}\n")

    proc = subprocess.Popen(
        train_cmd, shell=True, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)

    script_name = "sft_train" if mode == "sft" else "grpo_train"
    try:
        for line in proc.stdout:
            parser.parse_line(line)
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n\nInterrupted.")
        return 130

    rc = proc.wait()
    if isinstance(parser, GRPOLogParser):
        parser.summary()
    if rc == 0:
        print(f"\n{mode.upper()} training complete!")
    else:
        print(f"\n{mode.upper()} training failed (exit code {rc})")
    return rc


def launch_training(args: argparse.Namespace, mode: str) -> int:
    """Launch SFT or GRPO training on remote or local."""
    if not args.remote:
        return launch_local_training(args, mode)

    host, port = parse_remote(args.remote)

    # 1. Check GPUs
    print(f"Checking GPUs on {host}...")
    gpus = check_gpus(host, port)
    print_gpu_table(gpus, min_free_mb=args.min_free_mb)

    available = select_gpus(gpus, args.gpus, min_free_mb=args.min_free_mb)
    if not available:
        print("ERROR: No GPUs with sufficient free memory "
              f"(need {args.min_free_mb}MB)")
        return 1

    total_free = sum(g.free_mb for g in gpus if g.index in available)
    print(f"Selected GPUs: {','.join(str(g) for g in available)} "
          f"({total_free/1024:.1f}GB free)")

    # 2. Auto-sync code (include data/ for SFT)
    rsync_project(host, port, args.remote_dir,
                  include_data=(mode == "sft"))

    # 3. Build remote command
    gpu_ids = ",".join(str(g) for g in available)
    env_prefix = build_env_prefix(args.remote_dir, gpu_ids)

    if mode == "sft":
        train_cmd = build_sft_cmd(args)
        parser = SFTLogParser(
            total_epochs=args.epochs, verbose=args.verbose)
    else:
        train_cmd = build_grpo_cmd(args)
        parser = GRPOLogParser(verbose=args.verbose)

    # Multi-GPU: wrap with accelerate launch
    num_gpus = len(available)
    if num_gpus > 1 and mode == "sft":
        # Replace "python3 scripts/..." with "accelerate launch --num_processes N scripts/..."
        train_cmd = train_cmd.replace(
            "python3 scripts/", f"accelerate launch --num_processes {num_gpus} scripts/")

    # Save log file on remote — training writes to file, survives SSH drops
    output_name = Path(args.output).name if args.output else mode
    log_file = f"/tmp/{mode}_{output_name}.log"
    # nohup + redirect: training runs independently of SSH session
    cmd = (f"{env_prefix}nohup {train_cmd} > {shlex.quote(log_file)} 2>&1 &"
           f" TRAIN_PID=$!; echo \"PID=$TRAIN_PID\";"
           f" tail --pid=$TRAIN_PID -f {shlex.quote(log_file)}")

    # 4. Launch and stream
    print(f"\nLaunching {mode.upper()} training...")
    print(f"  Remote: {host}:{port}")
    print(f"  GPUs: {gpu_ids}")
    print(f"  Log: {log_file}")
    print(f"  Command: {train_cmd}\n")

    proc = ssh_run(host, port, cmd)
    script_name = "sft_train" if mode == "sft" else "grpo_train"

    try:
        for line in proc.stdout:
            parser.parse_line(line)
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n\nInterrupted. Remote training continues in background.")
        print(f"  Log: {log_file}")
        print(f"  To check: python3 scripts/train.py status --remote ...")
        print(f"  To kill:  ssh -p {port} {host} "
              f"'pkill -f {script_name}'")
        return 130

    rc = proc.wait()

    # Print summary
    if isinstance(parser, GRPOLogParser):
        parser.summary()

    if rc == 0:
        print(f"\n{mode.upper()} training complete!")
        if isinstance(parser, SFTLogParser) and parser.metrics:
            first = parser.metrics[0]["loss"]
            last = parser.metrics[-1]["loss"]
            print(f"  Loss: {first:.4f} → {last:.4f}")
    else:
        print(f"\n{mode.upper()} training failed (exit code {rc})")
    return rc


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    """Show GPU status and running training jobs."""
    if not args.remote:
        print("ERROR: --remote is required")
        return 1
    host, port = parse_remote(args.remote)

    gpus = check_gpus(host, port)
    print_gpu_table(gpus, min_free_mb=args.min_free_mb)

    # Check for running training processes
    result = ssh_run(
        host, port,
        "ps aux | grep -E '(sft_train|grpo_train)' | grep -v grep",
        capture=True, timeout=10)
    if result.stdout.strip():
        print("Running training jobs:")
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            pid = parts[1]
            cpu = parts[2]
            mem = parts[3]
            cmd_parts = " ".join(parts[10:])
            print(f"  PID {pid}  CPU={cpu}%  MEM={mem}%  {cmd_parts[:80]}")
    else:
        print("No training jobs running.")
    print()
    return 0


def _detect_log_type(log_path: str) -> str:
    """Detect whether a log file is from GRPO or SFT training."""
    if "sft" in log_path.lower():
        return "sft"
    return "grpo"


def _find_latest_log(host: str, port: int) -> str | None:
    """Find the most recent training log on remote."""
    result = ssh_run(host, port,
                     "ls -t /tmp/grpo_*.log /tmp/sft_*.log 2>/dev/null | head -1",
                     capture=True, timeout=10)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def cmd_logs(args: argparse.Namespace) -> int:
    """Show parsed training log (snapshot, not streaming)."""
    if not args.remote:
        print("ERROR: --remote is required")
        return 1
    host, port = parse_remote(args.remote)

    log_path = args.log
    if not log_path:
        log_path = _find_latest_log(host, port)
        if not log_path:
            print("ERROR: No training logs found on remote. "
                  "Use --log to specify a path.")
            return 1
        print(f"Using latest log: {log_path}")

    result = ssh_run(host, port, f"cat {shlex.quote(log_path)}",
                     capture=True, timeout=30)
    if result.returncode != 0:
        print(f"ERROR: Cannot read {log_path}")
        return 1

    log_type = _detect_log_type(log_path)
    if log_type == "sft":
        parser = SFTLogParser(
            total_epochs=getattr(args, "epochs", 8), verbose=args.verbose)
    else:
        parser = GRPOLogParser(verbose=args.verbose)
    for line in result.stdout.split("\n"):
        parser.parse_line(line)
    if isinstance(parser, GRPOLogParser):
        parser.summary()
    elif isinstance(parser, SFTLogParser) and parser.metrics:
        print(f"\nSFT Summary: {len(parser.metrics)} checkpoints logged")
        print(f"  Loss: {parser.metrics[0]['loss']:.4f} → "
              f"{parser.metrics[-1]['loss']:.4f}")
    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    """Monitor a running training job by tailing its log."""
    if not args.remote:
        print("ERROR: --remote is required")
        return 1
    host, port = parse_remote(args.remote)

    log_path = args.log
    if not log_path:
        log_path = _find_latest_log(host, port)
        if not log_path:
            print("ERROR: No training logs found. Use --log to specify.")
            return 1
        print(f"Using latest log: {log_path}")

    print(f"Monitoring {log_path} on {host}...")

    log_type = _detect_log_type(log_path)
    if log_type == "sft":
        parser = SFTLogParser(
            total_epochs=getattr(args, "epochs", 8), verbose=args.verbose)
    else:
        parser = GRPOLogParser(verbose=args.verbose)
    proc = ssh_run(host, port, f"tail -f {shlex.quote(log_path)}")

    try:
        for line in proc.stdout:
            parser.parse_line(line)
    except KeyboardInterrupt:
        proc.terminate()
        parser.summary()
        return 0

    return proc.wait()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def add_remote_args(parser: argparse.ArgumentParser) -> None:
    """Add common remote execution args."""
    remote = parser.add_argument_group("remote execution")
    remote.add_argument("--remote", metavar="USER@HOST:PORT",
                        help="SSH target (or set $GPU_SSH)")
    remote.add_argument("--remote-dir", default="~/MemoryGym",
                        help="Project dir on remote (default: ~/MemoryGym)")
    remote.add_argument("--gpus", default="auto",
                        help="GPU IDs, e.g. '0,1' (default: auto)")
    remote.add_argument("--min-free-mb", type=int, default=8000,
                        help="Min free VRAM (MB) for GPU (default: 8000)")
    remote.add_argument("--verbose", "-v", action="store_true",
                        help="Show all output lines")


def main():
    parser = argparse.ArgumentParser(
        description="MemoryGym training — SFT, GRPO, remote/local",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check remote GPU status
  python scripts/train.py status --remote $GPU_SSH

  # Remote SFT training (auto-sync + auto-GPU)
  python scripts/train.py sft --remote $GPU_SSH --model /path/to/Qwen3-4B --lora

  # Remote GRPO training
  python scripts/train.py grpo --remote $GPU_SSH \\
      --model /path/to/Qwen3-4B --adapter checkpoints/sft \\
      --steps 10 --group-size 4

  # Monitor running GRPO job
  python scripts/train.py monitor --remote $GPU_SSH --log /tmp/grpo.log
""")
    subparsers = parser.add_subparsers(dest="command", help="Training mode")

    # --- status ---
    p_status = subparsers.add_parser("status", help="Show GPU status")
    add_remote_args(p_status)

    # --- logs ---
    p_logs = subparsers.add_parser("logs",
                                    help="Show parsed training log")
    add_remote_args(p_logs)
    p_logs.add_argument("--log", help="Log file path on remote")

    # --- monitor ---
    p_monitor = subparsers.add_parser("monitor",
                                       help="Monitor running job (streaming)")
    add_remote_args(p_monitor)
    p_monitor.add_argument("--log", help="Log file path on remote")

    # --- sft ---
    p_sft = subparsers.add_parser("sft", help="SFT training")
    add_remote_args(p_sft)
    sft_train = p_sft.add_argument_group("SFT options")
    sft_train.add_argument("--model", required=True,
                           help="Base model path")
    sft_train.add_argument("--data", default=None,
                           help="SFT JSONL data (auto-generate if omitted)")
    sft_train.add_argument("--output", default="checkpoints/sft",
                           help="Output directory")
    sft_train.add_argument("--lora", action="store_true",
                           help="Use LoRA fine-tuning")
    sft_train.add_argument("--lora-rank", type=int, default=64,
                           help="LoRA rank")
    sft_train.add_argument("--epochs", type=int, default=3,
                           help="Training epochs")
    sft_train.add_argument("--batch-size", type=int, default=1,
                           help="Per-device batch size")
    sft_train.add_argument("--grad-accum", type=int, default=8,
                           help="Gradient accumulation steps")
    sft_train.add_argument("--lr", type=float, default=2e-5,
                           help="Learning rate")
    sft_train.add_argument("--max-length", type=int, default=4096,
                           help="Max sequence length")
    sft_train.add_argument("--bf16", action="store_true", default=True,
                           help="Use bfloat16")

    # --- grpo ---
    p_grpo = subparsers.add_parser("grpo", help="GRPO RL training")
    add_remote_args(p_grpo)
    grpo_train = p_grpo.add_argument_group("GRPO options")
    grpo_train.add_argument("--model", required=True,
                            help="Base model path")
    grpo_train.add_argument("--adapter", default=None,
                            help="SFT adapter to load and merge")
    grpo_train.add_argument("--output", default="checkpoints/grpo",
                            help="Output directory")
    grpo_train.add_argument("--lora-rank", type=int, default=16,
                            help="LoRA rank for GRPO adapter")
    grpo_train.add_argument("--steps", type=int, default=10,
                            help="Training steps")
    grpo_train.add_argument("--group-size", type=int, default=4,
                            help="Episodes per scenario (G)")
    grpo_train.add_argument("--groups-per-step", type=int, default=2,
                            help="Scenario groups per step")
    grpo_train.add_argument("--tier", default="lite",
                            choices=["lite", "standard"],
                            help="Evaluation tier")
    grpo_train.add_argument("--templates", nargs="+",
                            default=None,
                            help="Templates to use")
    grpo_train.add_argument("--max-turns", type=int, default=40,
                            help="Max turns per episode")
    grpo_train.add_argument("--max-new-tokens", type=int, default=256,
                            help="Max new tokens per generation")
    grpo_train.add_argument("--max-length", type=int, default=4096,
                            help="Max sequence length for training")
    grpo_train.add_argument("--lr", type=float, default=5e-6,
                            help="Learning rate")
    grpo_train.add_argument("--kl-coeff", type=float, default=0.05,
                            help="KL penalty coefficient (0 to disable)")
    grpo_train.add_argument("--ips", action="store_true",
                            help="Enable IPS-GRPO: inverse probability scaling")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Load .env file for GPU_SSH and other config
    _load_env()

    # Resolve $GPU_SSH from env if --remote not explicitly given
    if hasattr(args, "remote") and not args.remote:
        import os
        gpu_ssh = os.environ.get("GPU_SSH")
        if gpu_ssh:
            args.remote = gpu_ssh

    if args.command == "status":
        return cmd_status(args)
    elif args.command == "logs":
        return cmd_logs(args)
    elif args.command == "monitor":
        return cmd_monitor(args)
    elif args.command == "sft":
        return launch_training(args, "sft")
    elif args.command == "grpo":
        return launch_training(args, "grpo")
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
