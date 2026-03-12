"""Multi-agent team world template.

Entities: Autonomous agents with 23 possible attributes (6 dtype coverage).
Names: 30 prefixes × 20 suffixes = 600 unique agents.
Roles: 12 agent roles.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

import math
from random import Random
from typing import Any

from .base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate,
    _possessive,
)

_PREFIXES = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
    "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
    "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
    "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray",
    "Yankee", "Zulu", "Omega", "Sigma", "Theta", "Epsilon",
]

_SUFFIXES = [
    "Agent", "Worker", "Node", "Unit", "Bot", "Daemon",
    "Service", "Handler", "Processor", "Executor", "Monitor",
    "Router", "Dispatcher", "Scheduler", "Planner", "Evaluator",
    "Analyzer", "Synthesizer", "Coordinator", "Controller",
]

_ROLES = [
    "coordinator", "worker", "monitor", "router", "planner",
    "executor", "analyzer", "retriever", "generator", "validator",
    "debugger", "optimizer",
]

_SPECIALIZATIONS = [
    "handles real-time event stream processing and anomaly detection",
    "manages distributed task queues with priority-based scheduling",
    "performs continuous health monitoring of downstream services",
    "routes incoming requests across agent pools using load balancing",
    "orchestrates multi-step workflows with rollback capabilities",
    "executes batch data transformations on scheduled intervals",
    "analyzes system logs to identify performance bottlenecks",
    "retrieves and caches external API responses for other agents",
    "generates structured reports from aggregated telemetry data",
    "validates data integrity across distributed storage systems",
    "debugs failed transactions and recommends corrective actions",
    "optimizes resource allocation based on demand forecasting",
    "manages authentication tokens and session lifecycle tracking",
    "coordinates database migrations across multiple sharded clusters",
    "processes natural language queries and routes to specialist agents",
    "handles webhook ingestion and event fan-out to subscribers",
    "monitors SLA compliance and triggers escalation protocols",
    "performs automated rollback when deployment health checks fail",
    "synchronizes state across geo-distributed agent replicas",
    "manages circuit breaker patterns for fault-tolerant service calls",
]

_ERROR_DESCRIPTIONS = [
    "connection pool exhausted after sustained burst of incoming requests",
    "timeout waiting for downstream dependency to acknowledge heartbeat",
    "memory allocation failure during large batch processing operation",
    "certificate validation error on mutual TLS handshake with peer",
    "deserialization failure on malformed protobuf message from upstream",
    "deadlock detected in concurrent transaction processing pipeline",
    "rate limiter rejected requests exceeding configured throughput ceiling",
    "disk I/O latency spike caused write-ahead log flush to stall",
    "DNS resolution failure for service discovery endpoint",
    "out-of-order message sequence detected in event stream consumer",
    "schema migration conflict between rolling update replicas",
    "garbage collection pause exceeded acceptable latency threshold",
    "network partition isolated agent from consensus quorum",
    "token refresh loop triggered by clock skew between replicas",
    "queue consumer lag exceeded configured alert threshold",
    "corrupted checkpoint file prevented clean restart after crash",
    "thread pool saturation caused request queuing beyond SLA limits",
    "unexpected null reference in message routing decision tree",
    "configuration drift detected between canary and baseline replicas",
    "resource quota exceeded in container orchestration namespace",
]

_STATUSES = ["active", "idle", "error", "maintenance", "degraded"]
_PROTOCOLS = ["sync", "async", "pubsub", "streaming", "request-reply"]

_ATTR_DEFS = [
    # int (8)
    AttrDef("task_count", "int", 0, 5000, "", "Tasks processed"),
    AttrDef("message_count", "int", 0, 100000, "", "Messages exchanged"),
    AttrDef("retry_count", "int", 0, 500, "", "Retries"),
    AttrDef("queue_depth", "int", 0, 1000, "", "Queue depth"),
    AttrDef("uptime_hours", "int", 0, 8760, "", "Uptime (hours)"),
    AttrDef("active_connections", "int", 0, 500, "", "Active connections"),
    AttrDef("tool_call_count", "int", 0, 10000, "", "Tool calls"),
    AttrDef("context_switches", "int", 0, 2000, "", "Context switches"),
    # float (7)
    AttrDef("success_rate", "float", 0, 100, "%", "Success rate",
            agg_ops=("average",)),
    AttrDef("response_latency_ms", "float", 1, 5000, "ms",
            "Response latency"),
    AttrDef("cpu_utilization", "float", 0, 100, "%", "CPU utilization",
            agg_ops=("average",)),
    AttrDef("task_throughput", "float", 0.1, 100, "/hr",
            "Task throughput", agg_ops=("average",)),
    AttrDef("error_rate", "float", 0, 50, "%", "Error rate",
            agg_ops=("average",)),
    AttrDef("coordination_score", "float", 0, 100, "", "Coordination score",
            agg_ops=("average",)),
    AttrDef("memory_efficiency_pct", "float", 10, 100, "%",
            "Memory efficiency", agg_ops=("average",)),
    # text (2)
    AttrDef("specialization", "text", label="Specialization",
            text_pool=_SPECIALIZATIONS),
    AttrDef("last_error_description", "text", label="Last error",
            text_pool=_ERROR_DESCRIPTIONS),
    # enum (2)
    AttrDef("status", "enum", label="Status", choices=_STATUSES),
    AttrDef("communication_protocol", "enum", label="Communication protocol",
            choices=_PROTOCOLS),
    # date (2)
    AttrDef("deployed_date", "date", min_val=2023, max_val=2026,
            label="Deployed date"),
    AttrDef("last_heartbeat", "date", min_val=2026, max_val=2026,
            label="Last heartbeat"),
    # list_float (2)
    AttrDef("hourly_throughput", "list_float", min_val=0.1, max_val=200,
            label="Hourly throughput", list_len=5),
    AttrDef("error_burst", "list_float", min_val=0, max_val=50,
            label="Error burst rate (%)", list_len=5),
]

_Q_TEXTS: dict[str, list[str]] = {
    "task_count": [
        "How many tasks has {name} processed?",
        "What is {name}'s total task count?",
        "How many tasks has {name} handled so far?",
    ],
    "message_count": [
        "How many messages has {name} exchanged?",
        "What is {name}'s total message count?",
        "How many inter-agent messages has {name} sent or received?",
    ],
    "retry_count": [
        "How many retries has {name} performed?",
        "What is {name}'s retry count?",
        "How many times has {name} retried failed operations?",
    ],
    "queue_depth": [
        "What is {name}'s current queue depth?",
        "How deep is {name}'s task queue?",
        "How many items are queued for {name}?",
    ],
    "uptime_hours": [
        "How many hours has {name} been running?",
        "What is {name}'s uptime in hours?",
        "How long has {name} been operational?",
    ],
    "active_connections": [
        "How many active connections does {name} have?",
        "What is {name}'s active connection count?",
        "How many peers is {name} currently connected to?",
    ],
    "tool_call_count": [
        "How many tool calls has {name} made?",
        "What is {name}'s total tool call count?",
        "How many tool invocations has {name} performed?",
    ],
    "context_switches": [
        "How many context switches has {name} performed?",
        "What is {name}'s context switch count?",
        "How many times has {name} switched task contexts?",
    ],
    "success_rate": [
        "What is {name}'s success rate?",
        "What percentage of {name}'s tasks succeed?",
        "How reliable is {name} in completing tasks?",
    ],
    "response_latency_ms": [
        "What is {name}'s response latency?",
        "How fast does {name} respond in milliseconds?",
        "What latency does {name} exhibit per request?",
    ],
    "cpu_utilization": [
        "What is {name}'s CPU utilization?",
        "How much CPU does {name} consume?",
        "What percentage of CPU is {name} using?",
    ],
    "task_throughput": [
        "What is {name}'s task throughput?",
        "How many tasks does {name} complete per hour?",
        "What throughput does {name} sustain?",
    ],
    "error_rate": [
        "What is {name}'s error rate?",
        "What percentage of {name}'s operations fail?",
        "How often does {name} encounter errors?",
    ],
    "coordination_score": [
        "What is {name}'s coordination score?",
        "How well does {name} coordinate with other agents?",
        "What coordination rating has {name} received?",
    ],
    "memory_efficiency_pct": [
        "What is {name}'s memory efficiency?",
        "How efficiently does {name} use its memory budget?",
        "What memory efficiency percentage does {name} show?",
    ],
    "specialization": [
        "What does {name} specialize in?",
        "Describe {name}'s primary function.",
        "What is {name}'s specialization?",
    ],
    "last_error_description": [
        "What was {name}'s last error?",
        "Describe {name}'s most recent failure.",
        "What error did {name} last encounter?",
    ],
    "status": [
        "What is {name}'s current status?",
        "What operational state is {name} in?",
        "What is {name}'s health status?",
    ],
    "communication_protocol": [
        "What communication protocol does {name} use?",
        "How does {name} communicate with peers?",
        "What messaging protocol is {name} configured for?",
    ],
    "deployed_date": [
        "When was {name} deployed?",
        "What is {name}'s deployment date?",
        "When did {name} first go live?",
    ],
    "last_heartbeat": [
        "When was {name}'s last heartbeat?",
        "What is {name}'s most recent heartbeat timestamp?",
        "When did {name} last report in?",
    ],
    "hourly_throughput": [
        "What are {name}'s hourly throughput figures?",
        "List {name}'s throughput over the last 5 hours.",
        "What is {name}'s hour-by-hour throughput?",
    ],
    "error_burst": [
        "What are {name}'s error burst rates?",
        "List {name}'s error rates over the last 5 intervals.",
        "What is {name}'s error rate trend?",
    ],
}

_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "task_count": [
        ("has processed {val} tasks since deployment", "none"),
        ("task counts of {val} and {distractor} across monitoring windows",
         "temporal"),
        ("task tallies of {distractor} and {val} by different trackers",
         "qualified"),
    ],
    "message_count": [
        ("has exchanged {val} messages with peer agents", "none"),
        ("message counts of {val} and {distractor} in successive intervals",
         "temporal"),
        ("message tallies of {val} and {other_val} from different buses",
         "comparative"),
    ],
    "retry_count": [
        ("has retried failed operations {val} times", "none"),
        ("retry counts of {distractor} and {val} across deployment cycles",
         "temporal"),
        ("retry tallies of {val} and {distractor} by different monitors",
         "qualified"),
    ],
    "queue_depth": [
        ("currently has {val} items in its task queue", "none"),
        ("queue depths of {val} and {distractor} at different checkpoints",
         "temporal"),
        ("queue measurements of {distractor} and {val} from different probes",
         "qualified"),
    ],
    "uptime_hours": [
        ("has been running for {val} hours", "none"),
        ("uptime readings of {distractor} and {val} in different tracking systems",
         "temporal"),
        ("uptime figures of {val} and {other_val} from separate monitors",
         "comparative"),
    ],
    "active_connections": [
        ("maintains {val} active connections to peer agents", "none"),
        ("connection counts of {val} and {distractor} across health checks",
         "temporal"),
        ("connection tallies of {distractor} and {val} by different dashboards",
         "qualified"),
    ],
    "tool_call_count": [
        ("has made {val} tool calls during its lifecycle", "none"),
        ("tool call counts of {val} and {distractor} in successive windows",
         "temporal"),
        ("tool call tallies of {val} and {other_val} from separate audits",
         "comparative"),
    ],
    "context_switches": [
        ("has performed {val} context switches between tasks", "none"),
        ("context switch counts of {distractor} and {val} across epochs",
         "temporal"),
        ("switch tallies of {val} and {distractor} by different schedulers",
         "qualified"),
    ],
    "success_rate": [
        ("achieves a {val} success rate on completed tasks", "none"),
        ("success rates of {val} and {distractor} in different evaluation windows",
         "temporal"),
        ("success readings of {distractor} and {val} under different workloads",
         "qualified"),
    ],
    "response_latency_ms": [
        ("responds with an average latency of {val}", "none"),
        ("latency measurements of {val} and {distractor} across load profiles",
         "temporal"),
        ("response times of {distractor} and {val} under different conditions",
         "qualified"),
    ],
    "cpu_utilization": [
        ("runs at {val} CPU utilization", "none"),
        ("CPU readings of {val} and {distractor} across monitoring intervals",
         "temporal"),
        ("utilization figures of {val} and {other_val} from different meters",
         "comparative"),
    ],
    "task_throughput": [
        ("sustains a throughput of {val} tasks per hour", "none"),
        ("throughput readings of {distractor} and {val} in different windows",
         "temporal"),
        ("throughput estimates of {val} and {other_val} from different methods",
         "comparative"),
    ],
    "error_rate": [
        ("experiences an error rate of {val}", "none"),
        ("error rates of {val} and {distractor} across deployment versions",
         "temporal"),
        ("error measurements of {distractor} and {val} under different loads",
         "qualified"),
    ],
    "coordination_score": [
        ("holds a coordination score of {val}", "none"),
        ("coordination scores of {val} and {distractor} in successive reviews",
         "temporal"),
        ("coordination ratings of {distractor} and {val} by different evaluators",
         "qualified"),
    ],
    "memory_efficiency_pct": [
        ("operates at {val} memory efficiency", "none"),
        ("memory efficiency readings of {val} and {distractor} across cycles",
         "temporal"),
        ("efficiency figures of {distractor} and {val} by different profilers",
         "qualified"),
    ],
    "specialization": [
        ("{val}", "none"),
    ],
    "last_error_description": [
        ("{val}", "none"),
    ],
    "status": [
        ("is currently in {val} state", "none"),
    ],
    "communication_protocol": [
        ("communicates using the {val} protocol", "none"),
    ],
    "deployed_date": [
        ("was first deployed on {val}", "none"),
    ],
    "last_heartbeat": [
        ("last sent a heartbeat on {val}", "none"),
    ],
    "hourly_throughput": [
        ("recorded hourly throughput of {val}", "none"),
    ],
    "error_burst": [
        ("showed error burst rates of {val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("task_count", "uptime_hours", "tasks processed per hour of uptime"),
    ("message_count", "task_count", "messages per task"),
    ("retry_count", "task_count", "retries per task"),
    ("tool_call_count", "task_count", "tool calls per task"),
    ("error_rate", "cpu_utilization", "error-to-CPU ratio"),
    ("context_switches", "active_connections",
     "context switches per connection"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("success_rate", "cpu_utilization", "error_rate",
                "memory_efficiency_pct"):
        return f"{val:.1f}%" if isinstance(val, (int, float)) else str(val)
    if attr == "response_latency_ms":
        return f"{val:.1f}ms" if isinstance(val, (int, float)) else str(val)
    if attr == "task_throughput":
        return f"{val:.1f}/hr" if isinstance(val, (int, float)) else str(val)
    if attr == "coordination_score":
        return f"{val:.1f}" if isinstance(val, (int, float)) else str(val)
    if attr in ("task_count", "message_count", "tool_call_count"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr == "hourly_throughput" and isinstance(val, list):
        return ", ".join(f"{v:.1f}/hr" for v in val)
    if attr == "error_burst" and isinstance(val, list):
        return ", ".join(f"{v:.1f}%" for v in val)
    return str(val)


class AgentteamWorld(WorldTemplate):
    """Multi-agent ops — 600 names × 23 attrs × 12 roles."""

    @property
    def name(self) -> str:
        return "agentteam"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_ROLES)

    @property
    def entity_word(self) -> str:
        return "agent"

    @property
    def correction_rate(self) -> float:
        return 0.15  # highest — agent state is most dynamic

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.4, 0.7)

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.30,
            "comprehension": 0.35,
            "update": 0.20,
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(p, s) for p in _PREFIXES for s in _SUFFIXES]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{p} {s}" for p, s in selected]

    def _generate_list_float(self, adef, rng):
        """Pattern varies by attribute."""
        if adef.name == "hourly_throughput":
            # Sinusoidal load with occasional spike
            base = rng.uniform(adef.min_val * 2, adef.max_val * 0.4)
            values = []
            for i in range(adef.list_len):
                t = i / max(1, adef.list_len - 1)
                # Sine wave: day/night cycle simulation
                mult = 0.6 + 0.4 * math.sin(math.pi * t)
                noise = rng.uniform(0.85, 1.15)
                val = base * mult * noise
                # 20% chance of burst spike (3-5x)
                if rng.random() < 0.20:
                    val *= rng.uniform(3.0, 5.0)
                val = max(adef.min_val, min(adef.max_val, val))
                values.append(round(val, 2))
            return values
        # error_burst: incident-recovery pattern
        values = []
        spike_pos = rng.randint(0, adef.list_len - 1)
        spike_val = rng.uniform(adef.max_val * 0.5, adef.max_val * 0.9)
        baseline = rng.uniform(adef.min_val, adef.max_val * 0.1)
        for i in range(adef.list_len):
            if i == spike_pos:
                val = spike_val
            elif i > spike_pos:
                # Exponential decay after spike
                decay = math.exp(-(i - spike_pos) * 1.2)
                val = baseline + (spike_val - baseline) * decay
            else:
                val = baseline * rng.uniform(0.7, 1.3)
            val = max(adef.min_val, min(adef.max_val, val))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)

        # Constraint 2: cpu_utilization ↔ response_latency_ms
        if "cpu_utilization" in attrs and "response_latency_ms" in attrs:
            cpu = attrs["cpu_utilization"]
            if cpu > 80 and attrs["response_latency_ms"] < 500:
                attrs["response_latency_ms"] = round(
                    rng.uniform(500, 3000), 2)
            elif cpu < 20 and attrs["response_latency_ms"] > 200:
                attrs["response_latency_ms"] = round(
                    rng.uniform(1, 200), 2)

        # Constraint 3: status cascade for "error" state
        if "status" in attrs and attrs["status"] == "error":
            if "error_rate" in attrs:
                attrs["error_rate"] = round(
                    max(20, attrs["error_rate"]), 2)
            if "queue_depth" in attrs:
                attrs["queue_depth"] = max(100, attrs["queue_depth"])
            if "success_rate" in attrs:
                attrs["success_rate"] = round(
                    min(50, attrs["success_rate"]), 2)

        # Constraint 1: success_rate + error_rate ∈ [85, 110]
        # Applied after C3 to avoid C3 breaking the invariant
        if "success_rate" in attrs and "error_rate" in attrs:
            total = attrs["success_rate"] + attrs["error_rate"]
            if total < 85 or total > 110:
                target_total = rng.uniform(90, 105)
                new_error = target_total - attrs["success_rate"]
                if new_error > 50:
                    attrs["error_rate"] = 50.0
                    attrs["success_rate"] = round(target_total - 50, 2)
                elif new_error < 0:
                    attrs["error_rate"] = 0.0
                    attrs["success_rate"] = round(
                        min(100, target_total), 2)
                else:
                    attrs["error_rate"] = round(new_error, 2)

        # Constraint 4: task_throughput ↔ active_connections
        if "task_throughput" in attrs and "active_connections" in attrs:
            conns = attrs["active_connections"]
            tp = attrs["task_throughput"]
            if conns > 0:
                lo = conns * 0.05
                hi = conns * 2
                if tp < lo or tp > hi:
                    attrs["task_throughput"] = round(
                        rng.uniform(max(0.1, lo), max(0.2, hi)), 2)

        # Constraint 5: high uptime + high retry → low memory efficiency
        if ("uptime_hours" in attrs and "retry_count" in attrs
                and "memory_efficiency_pct" in attrs):
            if (attrs["uptime_hours"] > 8000
                    and attrs["retry_count"] > 200):
                attrs["memory_efficiency_pct"] = round(
                    min(50, attrs["memory_efficiency_pct"]), 2)

        # Constraint 6: coordination_score ↔ message_count/task_count
        if ("coordination_score" in attrs and "message_count" in attrs
                and "task_count" in attrs):
            tc = attrs["task_count"]
            if tc > 0:
                ratio = attrs["message_count"] / tc
                if attrs["coordination_score"] > 80 and ratio < 5:
                    attrs["message_count"] = rng.randint(
                        tc * 5, tc * 20)

        return EntitySpec(name=name, category=category, attrs=attrs)

    def enforce_constraints(self, entity: EntitySpec,
                            active_attrs: list[str],
                            rng: Random) -> None:
        attrs = entity.attrs
        # C2: cpu ↔ latency
        if "cpu_utilization" in attrs and "response_latency_ms" in attrs:
            cpu = attrs["cpu_utilization"]
            if cpu > 80 and attrs["response_latency_ms"] < 500:
                attrs["response_latency_ms"] = round(
                    rng.uniform(500, 3000), 2)
            elif cpu < 20 and attrs["response_latency_ms"] > 200:
                attrs["response_latency_ms"] = round(
                    rng.uniform(1, 200), 2)
        # C3: error state cascade
        if "status" in attrs and attrs["status"] == "error":
            if "error_rate" in attrs:
                attrs["error_rate"] = round(max(20, attrs["error_rate"]), 2)
            if "queue_depth" in attrs:
                attrs["queue_depth"] = max(100, attrs["queue_depth"])
            if "success_rate" in attrs:
                attrs["success_rate"] = round(
                    min(50, attrs["success_rate"]), 2)
        # C1: success + error ∈ [85, 110] (after C3)
        if "success_rate" in attrs and "error_rate" in attrs:
            total = attrs["success_rate"] + attrs["error_rate"]
            if total < 85 or total > 110:
                target = rng.uniform(90, 105)
                ne = target - attrs["success_rate"]
                if ne > 50:
                    attrs["error_rate"] = 50.0
                    attrs["success_rate"] = round(target - 50, 2)
                elif ne < 0:
                    attrs["error_rate"] = 0.0
                    attrs["success_rate"] = round(min(100, target), 2)
                else:
                    attrs["error_rate"] = round(ne, 2)
        # C4: throughput ↔ connections
        if "task_throughput" in attrs and "active_connections" in attrs:
            conns = attrs["active_connections"]
            if conns > 0:
                lo, hi = conns * 0.05, conns * 2
                if attrs["task_throughput"] < lo or attrs["task_throughput"] > hi:
                    attrs["task_throughput"] = round(
                        rng.uniform(max(0.1, lo), max(0.2, hi)), 2)
        # C5: high uptime + high retry → low memory efficiency
        if ("uptime_hours" in attrs and "retry_count" in attrs
                and "memory_efficiency_pct" in attrs):
            if attrs["uptime_hours"] > 8000 and attrs["retry_count"] > 200:
                attrs["memory_efficiency_pct"] = round(
                    min(50, attrs["memory_efficiency_pct"]), 2)
        # C6: coordination ↔ message/task ratio
        if ("coordination_score" in attrs and "message_count" in attrs
                and "task_count" in attrs):
            tc = attrs["task_count"]
            if tc > 0 and attrs["coordination_score"] > 80:
                if attrs["message_count"] / tc < 5:
                    attrs["message_count"] = rng.randint(tc * 5, tc * 20)

    def _format_value(self, attr: str, val: Any) -> str:
        return _fmt(attr, val)

    def _sentence_templates(self):
        return {attr: [SentenceTemplate(t, attr, d) for t, d in tmpls]
                for attr, tmpls in _SENTENCE_TMPLS.items()}

    def _ratio_pairs(self):
        return list(_RATIO_PAIRS)

    def _relationship_types(self):
        return [
            ("delegates_to", "delegates tasks to", False),
            ("shares_queue_with", "shares a task queue with", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "delegates_to":
            return (f"{rel.source} delegates overflow tasks to {rel.target} "
                    f"when its queue depth exceeds capacity thresholds.")
        if rel.relation == "shares_queue_with":
            return (f"{rel.source} and {rel.target} share a common task "
                    f"queue for load-balanced processing.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
        style = rng.choice([
            "health_report", "incident_log",
            "capacity_review", "orchestration_brief",
        ])
        header = {
            "health_report": (
                f"AGENT HEALTH REPORT — {entity.name}\n"
                f"Role: {entity.category}\n"),
            "incident_log": (
                f"INCIDENT LOG — {entity.name}\n"
                f"Role: {entity.category}\n"),
            "capacity_review": (
                f"CAPACITY REVIEW — {entity.name}\n"
                f"Role: {entity.category}\n"),
            "orchestration_brief": (
                f"ORCHESTRATION BRIEF — {entity.name}\n"
                f"Role: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION NOTICE: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following an operational review."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
