# trainer — Tasks

## P0 — GRPO v4a Experiment (BLOCKED: GPU SSH)

All code prep done (5 commits across loops 1-4). Waiting for GPU access.

Experiment command:
```
python -m memorygym.training grpo \
  --model Qwen/Qwen2.5-3B-Instruct \
  --tier standard --rollout-max-tokens 6144 \
  --ips --kl-coeff 0.05 --turn-level \
  --steps 3 --group-size 2 --groups-per-step 1 \
  -o runs/grpo_v4a_3step
```

## No remaining local tasks

All idle work exhausted:
- ~~SFT data quality review~~ ✅ (data is good, SFT signal too weak)
- ~~ROLE.md self-evolution~~ ✅
- ~~F28 Training-Free GRPO~~ assessed, not suitable for paper (prompt not weights)
- ~~RC1 system prompt contradiction~~ ✅ (stream_agent.py Edit cost now matches eval_task.py)
- Entering light mode until GPU access or new inbox
