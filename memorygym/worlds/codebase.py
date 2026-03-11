"""Codebase/software-system world template.

Entities: Software modules/services with 23 possible attributes (9 int + 7 float + 2 enum + 2 text + 2 list_float + 1 date).
Names: 30 function-words × 20 architecture-words = 600 unique modules.
Categories: 8 system types.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures on base class:
- "Lower is better" attrs (open_bugs, error_rate_pct, avg_response_ms) alongside "higher is better" (test_coverage_pct, uptime_pct)
- Tightly coupled constraints (test_count ↔ LOC, coverage ↔ bugs, status ↔ deployment, CPU ↔ response time)
- Two list_float with different patterns: deploys (random spikes) vs error_rate (incident spike + recovery)
- Real-world scenario: AI dev assistant managing a large codebase
"""

from __future__ import annotations

from random import Random
from typing import Any

from .base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate,
    _possessive,
)

_FUNCTION_WORDS = [
    "Auth", "Cache", "Config", "Data", "Event", "File", "Graph",
    "Index", "Job", "Key", "Log", "Mesh", "Node", "Object",
    "Parse", "Queue", "Route", "Schema", "Task", "User",
    "Vault", "Watch", "Proxy", "Metric", "Sync", "Token",
    "Stream", "Batch", "Alert", "Deploy",
]

_ARCH_WORDS = [
    "Gateway", "Pipeline", "Manager", "Engine", "Service",
    "Handler", "Worker", "Bridge", "Adapter", "Controller",
    "Scheduler", "Resolver", "Processor", "Dispatcher", "Monitor",
    "Registry", "Connector", "Validator", "Transformer", "Aggregator",
]

_CATEGORIES = [
    "Backend Service", "Frontend Module", "Data Pipeline",
    "Infrastructure", "API Gateway", "ML Service",
    "DevOps Tool", "Shared Library",
]

_ARCHITECTURE_NOTES = [
    "event-driven architecture using Kafka message queues with horizontal scaling to 50 nodes",
    "monolithic legacy service being gradually decomposed into microservices via strangler fig pattern",
    "serverless deployment on AWS Lambda with DynamoDB for state, triggered by API Gateway events",
    "gRPC-based service mesh with Envoy sidecar proxies and mutual TLS for inter-service communication",
    "CQRS pattern with separate read and write models backed by PostgreSQL and Elasticsearch",
    "real-time streaming pipeline built on Apache Flink with exactly-once semantics and Kafka sources",
    "GraphQL federation layer aggregating data from 12 downstream microservices into a unified schema",
    "container-orchestrated via Kubernetes with Helm charts, auto-scaling based on CPU and custom metrics",
    "batch processing system using Apache Spark for ETL jobs, scheduled via Airflow DAGs",
    "edge computing module deployed on IoT gateways with local inference and cloud sync via MQTT",
    "multi-tenant SaaS architecture with tenant isolation at the database level using row-level security",
    "plugin-based architecture allowing third-party extensions via a well-defined SDK and sandboxed runtime",
    "reactive microservice using Spring WebFlux with non-blocking I/O and backpressure support",
    "distributed cache layer with consistent hashing across Redis Cluster nodes and write-through policy",
    "feature flag service providing A/B testing, gradual rollouts, and kill switches for all platform services",
    "CI/CD pipeline orchestrator managing build, test, and deploy stages across multiple cloud providers",
    "machine learning inference service with model versioning, A/B testing, and automatic rollback on drift",
    "data lake architecture on S3 with Iceberg tables, supporting both batch and streaming ingestion",
    "zero-trust security module implementing OAuth2, RBAC, and attribute-based access control policies",
    "observability platform collecting metrics, traces, and logs with OpenTelemetry and Grafana dashboards",
]

_KNOWN_ISSUES = [
    "connection pool exhaustion under sustained load above 2K RPS, temporary mitigation via increased pool size",
    "memory leak in image processing pipeline when handling malformed TIFF files, accumulates over 48 hours",
    "race condition in distributed lock acquisition causes occasional duplicate job execution across workers",
    "N+1 query problem in user profile endpoint, causes 500ms latency spikes during peak hours",
    "TLS certificate rotation fails silently when intermediate CA is expired, requires manual intervention",
    "database migration rollback script missing for the last three schema changes, blocks safe deployment",
    "Kafka consumer group rebalancing during deployments causes 30-second message processing gaps",
    "intermittent timeout on cross-region API calls due to DNS resolution caching mismatch",
    "log rotation not configured for audit logs, disk usage growing at 2GB per day on production nodes",
    "GraphQL query depth not limited, allowing malicious queries to cause exponential resolver fan-out",
    "webhook retry logic uses fixed 5-second interval instead of exponential backoff, hammering failed endpoints",
    "feature flag evaluation cache stale for up to 60 seconds, causing inconsistent user experience during rollouts",
    "batch job checkpoint mechanism corrupts state file when process receives SIGKILL during write",
    "API rate limiter counts pre-auth requests against authenticated user quotas due to middleware ordering",
    "search index rebuild takes 4 hours and blocks write operations, needs online reindexing strategy",
    "session token stored in localStorage instead of httpOnly cookie, XSS vulnerability documented but unpatched",
    "health check endpoint returns 200 even when downstream database is unreachable, misleading load balancer",
    "CSV export generates files exceeding 2GB for large tenants, causing out-of-memory errors in the browser",
    "cron job scheduling drift accumulates over weeks due to fixed-delay instead of fixed-rate execution",
    "service discovery cache not invalidated on node removal, causing requests to decommissioned instances",
]

_LANGUAGES = ["python", "java", "go", "rust", "typescript", "kotlin"]

_STATUSES = ["active", "beta", "maintenance", "deprecated"]

_ATTR_DEFS = [
    # int (9)
    AttrDef("lines_of_code", "int", 50, 500000, "", "Lines of code"),
    AttrDef("test_count", "int", 0, 5000, "", "Test count"),
    AttrDef("open_bugs", "int", 0, 200, "", "Open bugs"),
    AttrDef("contributors", "int", 1, 50, "", "Contributors"),
    AttrDef("api_endpoints", "int", 0, 300, "", "API endpoints"),
    AttrDef("dependencies", "int", 1, 80, "", "Dependencies"),
    AttrDef("deployment_count", "int", 0, 2000, "", "Total deployments"),
    AttrDef("avg_response_ms", "int", 1, 5000, "ms", "Avg response time"),
    AttrDef("star_count", "int", 0, 10000, "", "Internal stars"),
    # float (7)
    AttrDef("test_coverage_pct", "float", 0, 99, "%", "Test coverage",
            agg_ops=("average",)),
    AttrDef("uptime_pct", "float", 90.0, 99.999, "%", "Uptime",
            agg_ops=("average",)),
    AttrDef("code_churn_pct", "float", 0.5, 30.0, "%", "Code churn rate",
            agg_ops=("average",)),
    AttrDef("tech_debt_hours", "float", 0, 2000, "hrs",
            "Technical debt (hours)"),
    AttrDef("memory_usage_mb", "float", 10, 16000, "MB", "Memory usage"),
    AttrDef("error_rate_pct", "float", 0, 15, "%", "Error rate",
            agg_ops=("average",)),
    AttrDef("cpu_utilization_pct", "float", 1, 95, "%", "CPU utilization",
            agg_ops=("average",)),
    # enum (2)
    AttrDef("primary_language", "enum", label="Primary language",
            choices=_LANGUAGES),
    AttrDef("status", "enum", label="Status", choices=_STATUSES),
    # text (2)
    AttrDef("architecture_notes", "text", label="Architecture notes",
            text_pool=_ARCHITECTURE_NOTES),
    AttrDef("known_issues", "text", label="Known issues",
            text_pool=_KNOWN_ISSUES),
    # list_float (2)
    AttrDef("weekly_deploys", "list_float", min_val=0, max_val=50,
            label="Weekly deployments (last 5 weeks)", list_len=5),
    AttrDef("error_rate_trend", "list_float", min_val=0, max_val=15,
            label="Error rate trend (last 5 periods)", list_len=5),
    # date (1)
    AttrDef("created_date", "date", min_val=2015, max_val=2026,
            label="Created date"),
]

_Q_TEXTS: dict[str, list[str]] = {
    "lines_of_code": [
        "How many lines of code does {name} have?",
        "What is {name}'s codebase size in LOC?",
        "How large is the {name} codebase?",
    ],
    "test_count": [
        "How many tests does {name} have?",
        "What is {name}'s test count?",
        "How many test cases are in {name}?",
    ],
    "open_bugs": [
        "How many open bugs does {name} have?",
        "What is {name}'s open bug count?",
        "How many unresolved bugs are tracked for {name}?",
    ],
    "contributors": [
        "How many contributors work on {name}?",
        "What is {name}'s contributor count?",
        "How many developers contribute to {name}?",
    ],
    "api_endpoints": [
        "How many API endpoints does {name} expose?",
        "What is {name}'s API endpoint count?",
        "How many endpoints does {name} serve?",
    ],
    "dependencies": [
        "How many dependencies does {name} have?",
        "What is {name}'s dependency count?",
        "How many packages does {name} depend on?",
    ],
    "deployment_count": [
        "How many times has {name} been deployed?",
        "What is {name}'s total deployment count?",
        "How many deployments has {name} undergone?",
    ],
    "avg_response_ms": [
        "What is {name}'s average response time?",
        "How fast does {name} respond on average?",
        "What is the average latency of {name}?",
    ],
    "star_count": [
        "How many internal stars does {name} have?",
        "What is {name}'s star count?",
        "How many stars has {name} received?",
    ],
    "test_coverage_pct": [
        "What is {name}'s test coverage?",
        "What percentage of {name}'s code is covered by tests?",
        "How high is {name}'s test coverage?",
    ],
    "uptime_pct": [
        "What is {name}'s uptime?",
        "What uptime does {name} maintain?",
        "How reliable is {name} in terms of availability?",
    ],
    "code_churn_pct": [
        "What is {name}'s code churn rate?",
        "How much of {name}'s code changes monthly?",
        "What is the monthly code churn for {name}?",
    ],
    "tech_debt_hours": [
        "How much technical debt does {name} carry?",
        "What is {name}'s tech debt in hours?",
        "How many hours of tech debt does {name} have?",
    ],
    "memory_usage_mb": [
        "How much memory does {name} use?",
        "What is {name}'s memory footprint?",
        "How much RAM does {name} consume?",
    ],
    "error_rate_pct": [
        "What is {name}'s error rate?",
        "What percentage of {name}'s requests result in errors?",
        "How high is {name}'s error rate?",
    ],
    "cpu_utilization_pct": [
        "What is {name}'s CPU utilization?",
        "How much CPU does {name} consume?",
        "What percentage of CPU does {name} use?",
    ],
    "primary_language": [
        "What programming language is {name} written in?",
        "What is {name}'s primary language?",
        "Which language is {name} built with?",
    ],
    "status": [
        "What is {name}'s current status?",
        "Is {name} active, beta, or deprecated?",
        "What lifecycle stage is {name} in?",
    ],
    "architecture_notes": [
        "Describe {name}'s architecture.",
        "What is {name}'s system architecture?",
        "How is {name} architected?",
    ],
    "known_issues": [
        "What known issues does {name} have?",
        "What are {name}'s current known problems?",
        "Describe any known issues with {name}.",
    ],
    "weekly_deploys": [
        "How many deployments has {name} had over the last 5 weeks?",
        "List {name}'s weekly deployment counts for the past 5 weeks.",
    ],
    "error_rate_trend": [
        "What has {name}'s error rate been over the last 5 periods?",
        "List {name}'s error rate trend for the past 5 periods.",
    ],
    "created_date": [
        "When was {name} created?",
        "What is {name}'s creation date?",
        "When was {name} first deployed?",
    ],
}

_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "lines_of_code": [
        ("contains {val} lines of code", "none"),
        ("codebase sizes of {distractor} and {val} LOC across audits",
         "temporal"),
        ("LOC counts of {val} and {other_val} from different static "
         "analysis tools", "comparative"),
    ],
    "test_count": [
        ("includes {val} automated tests", "none"),
        ("test counts of {val} and {distractor} before and after "
         "a refactoring sprint", "temporal"),
    ],
    "open_bugs": [
        ("has {val} open bugs in the tracker", "none"),
        ("bug counts of {distractor} and {val} in successive sprints",
         "temporal"),
        ("open bug figures of {val} and {other_val} from different "
         "tracking systems", "comparative"),
    ],
    "contributors": [
        ("is maintained by {val} contributors", "none"),
        ("contributor counts of {val} and {distractor} across quarters",
         "temporal"),
    ],
    "api_endpoints": [
        ("exposes {val} API endpoints", "none"),
        ("endpoint counts of {distractor} and {val} before and after "
         "an API version upgrade", "temporal"),
    ],
    "dependencies": [
        ("depends on {val} external packages", "none"),
        ("dependency counts of {val} and {distractor} in successive "
         "dependency audits", "temporal"),
    ],
    "deployment_count": [
        ("has been deployed {val} times since inception", "none"),
        ("deployment counts of {distractor} and {val} in different "
         "reporting periods", "temporal"),
    ],
    "avg_response_ms": [
        ("averages {val} ms response time", "none"),
        ("response time readings of {val} and {distractor} under "
         "different load conditions", "qualified"),
        ("latency figures of {distractor} and {val} from different "
         "monitoring tools", "comparative"),
    ],
    "star_count": [
        ("has received {val} internal stars from engineers", "none"),
    ],
    "test_coverage_pct": [
        ("achieves {val} test coverage", "none"),
        ("coverage figures of {val} and {distractor} across test "
         "runs", "temporal"),
        ("coverage readings of {distractor} and {val} from different "
         "coverage tools", "qualified"),
    ],
    "uptime_pct": [
        ("maintains {val} uptime over the reporting period", "none"),
        ("uptime figures of {distractor} and {val} in successive "
         "quarters", "temporal"),
    ],
    "code_churn_pct": [
        ("shows a monthly code churn rate of {val}", "none"),
        ("churn rates of {val} and {distractor} across quarters",
         "temporal"),
    ],
    "tech_debt_hours": [
        ("carries {val} hours of estimated technical debt", "none"),
        ("tech debt estimates of {distractor} and {val} from different "
         "assessments", "temporal"),
    ],
    "memory_usage_mb": [
        ("consumes {val} of memory in production", "none"),
        ("memory usage figures of {val} and {distractor} under different "
         "workloads", "qualified"),
    ],
    "error_rate_pct": [
        ("reports an error rate of {val}", "none"),
        ("error rates of {distractor} and {val} in successive monitoring "
         "windows", "temporal"),
    ],
    "cpu_utilization_pct": [
        ("runs at {val} CPU utilization", "none"),
        ("CPU utilization figures of {val} and {distractor} under "
         "peak and off-peak loads", "qualified"),
    ],
    "primary_language": [
        ("is implemented primarily in {val}", "none"),
    ],
    "status": [
        ("is currently in {val} status", "none"),
    ],
    "architecture_notes": [
        ("{val}", "none"),
    ],
    "known_issues": [
        ("has a documented issue: {val}", "none"),
    ],
    "weekly_deploys": [
        ("recorded weekly deployment counts of {val} over the last "
         "5 weeks", "none"),
    ],
    "error_rate_trend": [
        ("showed error rates of {val} over the last 5 periods", "none"),
    ],
    "created_date": [
        ("was first created on {val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("open_bugs", "lines_of_code", "bug density (bugs per KLOC)"),
    ("test_count", "lines_of_code", "test density"),
    ("lines_of_code", "contributors", "code per contributor"),
    ("memory_usage_mb", "lines_of_code", "memory per KLOC"),
    ("deployment_count", "contributors", "deploys per contributor"),
    ("api_endpoints", "dependencies", "endpoints per dependency"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("lines_of_code", "test_count", "deployment_count",
                "star_count"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr in ("open_bugs", "contributors", "api_endpoints",
                "dependencies"):
        return str(val)
    if attr == "avg_response_ms":
        return f"{val:,} ms" if isinstance(val, (int, float)) else str(val)
    if attr in ("test_coverage_pct", "code_churn_pct", "error_rate_pct",
                "cpu_utilization_pct"):
        return f"{val:.2f}%" if isinstance(val, (int, float)) else str(val)
    if attr == "uptime_pct":
        return f"{val:.3f}%" if isinstance(val, (int, float)) else str(val)
    if attr == "tech_debt_hours":
        return f"{val:,.0f} hrs" if isinstance(val, (int, float)) else str(val)
    if attr == "memory_usage_mb":
        return f"{val:,.1f} MB" if isinstance(val, (int, float)) else str(val)
    if attr == "weekly_deploys" and isinstance(val, list):
        return ", ".join(f"{v:.0f}" for v in val)
    if attr == "error_rate_trend" and isinstance(val, list):
        return ", ".join(f"{v:.2f}%" for v in val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class CodebaseWorld(WorldTemplate):
    """Software codebase — 600 modules × 23 attrs × 8 categories."""

    @property
    def name(self) -> str:
        return "codebase"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_CATEGORIES)

    @property
    def entity_word(self) -> str:
        return "module"

    @property
    def correction_rate(self) -> float:
        return 0.12  # high — software state changes frequently

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.4, 0.7)  # standard

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.30,       # need to recall module specs
            "comprehension": 0.35,   # high — bug density, ratio reasoning
            "update": 0.20,          # moderate corrections
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(f, a) for f in _FUNCTION_WORDS for a in _ARCH_WORDS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{f} {a}" for f, a in selected]

    def _generate_list_float(self, adef, rng):
        if adef.name == "weekly_deploys":
            # Random CI/CD rhythm with occasional spike (hotfix week)
            base = rng.uniform(2, 15)
            values = []
            for i in range(adef.list_len):
                # 20% chance of spike week (2-3x normal)
                if rng.random() < 0.2:
                    val = base * rng.uniform(2.0, 3.0)
                else:
                    val = base * rng.uniform(0.6, 1.4)
                val = max(adef.min_val, min(adef.max_val, val))
                values.append(round(val, 2))
            return values
        # error_rate_trend: stable baseline with possible incident spike + recovery
        base = rng.uniform(0.1, 3.0)
        spike_pos = rng.randint(1, adef.list_len - 2)  # spike not at edges
        values = []
        for i in range(adef.list_len):
            if i == spike_pos:
                val = base * rng.uniform(3.0, 5.0)  # incident spike
            elif i == spike_pos + 1:
                val = base * rng.uniform(1.2, 2.0)  # partial recovery
            else:
                val = base * rng.uniform(0.7, 1.3)  # normal
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

        loc = attrs.get("lines_of_code", 0)

        # Constraint 1: test_count / LOC ∈ [0.005, 0.15]
        if "test_count" in attrs and loc > 0:
            ratio = attrs["test_count"] / loc
            if ratio < 0.005 or ratio > 0.15:
                target = rng.uniform(0.01, 0.08)
                attrs["test_count"] = max(0, min(5000, round(loc * target)))

        # Constraint 2: coverage ↔ bugs (scaled by LOC)
        if "test_coverage_pct" in attrs and "open_bugs" in attrs:
            cov = attrs["test_coverage_pct"]
            if cov > 80:
                hi = min(30, max(1, loc // 5000)) if loc else 30
                attrs["open_bugs"] = rng.randint(0, hi)
            elif cov < 30:
                lo = min(150, max(1, loc // 2000)) if loc else 20
                attrs["open_bugs"] = rng.randint(lo, 200)

        # Constraint 3: LOC × contributors × code_churn (three-way)
        if ("lines_of_code" in attrs and "contributors" in attrs
                and "code_churn_pct" in attrs):
            cont = attrs["contributors"]
            if loc > 100000 and cont < 5:
                attrs["code_churn_pct"] = round(
                    min(attrs["code_churn_pct"], rng.uniform(0.5, 5.0)), 2)
            elif loc < 10000 and cont > 20:
                attrs["code_churn_pct"] = round(
                    max(attrs["code_churn_pct"], rng.uniform(10.0, 25.0)), 2)

        # Constraint 4: CPU ↔ response time positively correlated
        if "cpu_utilization_pct" in attrs and "avg_response_ms" in attrs:
            cpu = attrs["cpu_utilization_pct"]
            if cpu > 70:
                attrs["avg_response_ms"] = max(200, attrs["avg_response_ms"])
            elif cpu < 20:
                attrs["avg_response_ms"] = min(500, attrs["avg_response_ms"])

        # Constraint 5: memory ↔ LOC (bounded range)
        if "memory_usage_mb" in attrs and loc > 0:
            lo = max(10, loc / 100)
            hi = max(lo + 1, loc / 10)
            mem = attrs["memory_usage_mb"]
            if mem < lo or mem > hi:
                attrs["memory_usage_mb"] = round(
                    rng.uniform(lo, min(hi, 16000)), 1)

        # Constraint 6: uptime ↔ error_rate inversely related
        if "uptime_pct" in attrs and "error_rate_pct" in attrs:
            if attrs["uptime_pct"] > 99.9:
                attrs["error_rate_pct"] = round(
                    min(attrs["error_rate_pct"], rng.uniform(0, 0.5)), 2)

        # Constraint 7: deprecated cascade
        if "status" in attrs and attrs["status"] == "deprecated":
            if "deployment_count" in attrs:
                attrs["deployment_count"] = rng.randint(0, 100)
            if "code_churn_pct" in attrs:
                attrs["code_churn_pct"] = round(
                    rng.uniform(0.5, 2.0), 2)
            if "contributors" in attrs:
                attrs["contributors"] = rng.randint(1, 5)
            if "tech_debt_hours" in attrs:
                attrs["tech_debt_hours"] = round(
                    rng.uniform(500, 2000), 1)
            if "open_bugs" in attrs:
                attrs["open_bugs"] = max(20, attrs.get("open_bugs", 20))
            if "weekly_deploys" in attrs:
                vals = attrs["weekly_deploys"]
                if len(vals) >= 2:
                    vals[-1] = round(rng.uniform(0, 1), 2)
                    vals[-2] = round(rng.uniform(0, 1), 2)

        return EntitySpec(name=name, category=category, attrs=attrs)

    def _format_value(self, attr: str, val: Any) -> str:
        return _fmt(attr, val)

    def _sentence_templates(self):
        return {attr: [SentenceTemplate(t, attr, d) for t, d in tmpls]
                for attr, tmpls in _SENTENCE_TMPLS.items()}

    def _ratio_pairs(self):
        return list(_RATIO_PAIRS)

    def _relationship_types(self):
        return [
            ("depends_on", "depends on", False),
            ("maintained_by_same_team", "shares a team with", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "depends_on":
            return (f"{rel.source} depends on {rel.target} as a "
                    f"critical upstream dependency.")
        if rel.relation == "maintained_by_same_team":
            return (f"{rel.source} and {rel.target} are maintained "
                    f"by the same engineering team.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
        style = rng.choice(["profile", "incident", "review", "brief"])
        header = {
            "profile": (f"SERVICE PROFILE — {entity.name}\n"
                        f"Type: {entity.category}\n"),
            "incident": (f"INCIDENT REPORT — {entity.name}\n"
                         f"Category: {entity.category}\n"),
            "review": (f"CODE REVIEW SUMMARY — {entity.name}\n"
                       f"Classification: {entity.category}\n"),
            "brief": (f"STATUS BRIEF — {entity.name}\n"
                      f"System: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        if attr in ("error_rate_pct", "avg_response_ms",
                     "cpu_utilization_pct"):
            context = "following a production incident investigation"
        elif attr in ("lines_of_code", "dependencies", "test_count"):
            context = "after a codebase refactoring sprint"
        elif attr in ("contributors", "status"):
            context = "following a team restructure"
        else:
            context = "based on the latest monitoring report"
        return (
            f"SERVICE UPDATE: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"{context}."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
