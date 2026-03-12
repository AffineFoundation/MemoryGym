"""Project management world template.

Entities: Software projects with 23 possible attributes (6 dtype coverage).
Names: 30 prefixes × 20 suffixes = 600 unique projects.
Methodologies: 12 management approaches.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from .base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate,
    _possessive,
)

_PREFIXES = [
    "Phoenix", "Aurora", "Titan", "Nebula", "Horizon", "Catalyst",
    "Meridian", "Spectra", "Vanguard", "Axiom", "Zenith", "Summit",
    "Frontier", "Beacon", "Pinnacle", "Apex", "Nexus", "Vertex",
    "Quantum", "Helix", "Prism", "Nova", "Cobalt", "Onyx",
    "Argon", "Cipher", "Vector", "Flux", "Ember", "Pulse",
]

_SUFFIXES = [
    "Platform", "Engine", "Portal", "Hub", "Suite", "Gateway",
    "Framework", "Pipeline", "Toolkit", "Module", "Workspace",
    "Dashboard", "Orchestrator", "Connector", "Bridge", "Nexus",
    "Core", "Studio", "Forge", "Matrix",
]

_METHODOLOGIES = [
    "Agile", "Waterfall", "Kanban", "Scrum", "SAFe", "Lean",
    "XP", "Spiral", "DevOps", "Hybrid", "RAD", "FDD",
]

_PROJECT_DESCRIPTIONS = [
    "builds a real-time data pipeline for financial market analytics",
    "develops an AI-powered code review and quality assurance platform",
    "creates a distributed task orchestration engine for microservices",
    "implements a unified identity and access management solution",
    "designs a multi-tenant SaaS platform for supply chain visibility",
    "constructs an automated incident response and remediation system",
    "builds a natural language interface for database query generation",
    "develops a continuous integration platform with intelligent test selection",
    "creates a recommendation engine for personalized learning paths",
    "implements a real-time collaboration workspace with conflict resolution",
    "designs a privacy-preserving data analytics framework",
    "constructs a model serving infrastructure with auto-scaling",
    "builds a compliance monitoring dashboard for regulated industries",
    "develops a low-code workflow automation platform for enterprises",
    "creates a cross-platform mobile development toolkit with hot reload",
    "implements a distributed tracing and observability platform",
    "designs a federated search engine across heterogeneous data sources",
    "constructs an API gateway with rate limiting and circuit breaking",
    "builds an event-driven notification system with delivery guarantees",
    "develops a configuration management platform with drift detection",
]

_KEY_RISKS = [
    "single point of failure in the authentication microservice",
    "vendor lock-in with the cloud provider's proprietary ML pipeline",
    "regulatory compliance gap in cross-border data transfer handling",
    "critical dependency on an unmaintained open-source library",
    "insufficient load testing for projected peak traffic volumes",
    "data migration from legacy system may cause extended downtime",
    "key engineer departure risk with no documented knowledge transfer",
    "security vulnerability in third-party payment processing SDK",
    "scope creep from stakeholder feature requests without re-estimation",
    "database schema migration blocking backward compatibility",
    "CI/CD pipeline fragility causing frequent deployment rollbacks",
    "inadequate monitoring coverage for distributed transaction flows",
    "API versioning strategy conflicts with existing client contracts",
    "memory leak in long-running worker processes under sustained load",
    "incomplete disaster recovery plan for multi-region failover",
    "technical debt in authentication module delaying feature releases",
    "race condition in concurrent write paths to shared state store",
    "certificate expiration management across multiple service endpoints",
    "insufficient input validation at API boundary leading to injection risk",
    "cache invalidation logic causing stale reads during high-write periods",
]

_STATUSES = ["planning", "active", "on-hold", "completed", "cancelled"]
_PRIORITIES = ["critical", "high", "medium", "low"]

_ATTR_DEFS = [
    # int (7)
    AttrDef("team_size", "int", 2, 200, "", "Team size"),
    AttrDef("milestone_count", "int", 3, 50, "", "Milestones"),
    AttrDef("task_backlog", "int", 0, 5000, "", "Task backlog"),
    AttrDef("closed_issues", "int", 10, 50000, "", "Closed issues"),
    AttrDef("sprint_count", "int", 1, 100, "", "Sprints completed"),
    AttrDef("dependency_count", "int", 0, 200, "", "Dependencies"),
    AttrDef("stakeholder_count", "int", 1, 50, "", "Stakeholders"),
    AttrDef("release_count", "int", 0, 100, "", "Releases"),
    # float (7)
    AttrDef("completion_pct", "float", 0, 100, "%", "Completion",
            agg_ops=("average",)),
    AttrDef("budget_k", "float", 10, 5000, "$K", "Budget"),
    AttrDef("burn_rate_k", "float", 1, 500, "$K/mo", "Burn rate"),
    AttrDef("scope_change_pct", "float", 0, 80, "%", "Scope change",
            agg_ops=("average",)),
    AttrDef("velocity_points", "float", 1, 100, "", "Velocity (points/sprint)",
            agg_ops=("average",)),
    AttrDef("risk_score", "float", 0, 10, "", "Risk score",
            agg_ops=("average",)),
    AttrDef("budget_variance_pct", "float", -50, 50, "%", "Budget variance",
            agg_ops=("average",)),
    # text (2)
    AttrDef("project_description", "text", label="Project description",
            text_pool=_PROJECT_DESCRIPTIONS),
    AttrDef("key_risk", "text", label="Key risk",
            text_pool=_KEY_RISKS),
    # enum (2)
    AttrDef("status", "enum", label="Status", choices=_STATUSES),
    AttrDef("priority", "enum", label="Priority", choices=_PRIORITIES),
    # date (2)
    AttrDef("start_date", "date", min_val=2020, max_val=2026,
            label="Start date"),
    AttrDef("deadline", "date", min_val=2024, max_val=2027,
            label="Deadline"),
    # list_float (2)
    AttrDef("weekly_velocity", "list_float", min_val=1, max_val=100,
            label="Weekly sprint velocity", list_len=4),
    AttrDef("monthly_burn", "list_float", min_val=1, max_val=500,
            label="Monthly burn ($K)", list_len=5),
]

_Q_TEXTS: dict[str, list[str]] = {
    "team_size": [
        "How many people are on the {name} team?",
        "What is the team size for {name}?",
        "How large is {name}'s development team?",
    ],
    "milestone_count": [
        "How many milestones does {name} have?",
        "What is {name}'s total milestone count?",
        "How many milestones are defined for {name}?",
    ],
    "task_backlog": [
        "How many tasks are in {name}'s backlog?",
        "What is the backlog size for {name}?",
        "How many backlog items does {name} have?",
    ],
    "closed_issues": [
        "How many issues has {name} closed?",
        "What is {name}'s closed issue count?",
        "How many resolved issues does {name} have?",
    ],
    "sprint_count": [
        "How many sprints has {name} completed?",
        "What is {name}'s total sprint count?",
        "How many sprint cycles has {name} been through?",
    ],
    "dependency_count": [
        "How many dependencies does {name} have?",
        "What is {name}'s dependency count?",
        "How many external dependencies does {name} rely on?",
    ],
    "stakeholder_count": [
        "How many stakeholders does {name} have?",
        "What is {name}'s stakeholder count?",
        "How many stakeholders are involved in {name}?",
    ],
    "release_count": [
        "How many releases has {name} shipped?",
        "What is {name}'s total release count?",
        "How many versions has {name} published?",
    ],
    "completion_pct": [
        "What is {name}'s completion percentage?",
        "How complete is {name}?",
        "What percentage of {name} is finished?",
    ],
    "budget_k": [
        "What is {name}'s budget?",
        "How much budget is allocated to {name}?",
        "What is the total budget for {name} in thousands?",
    ],
    "burn_rate_k": [
        "What is {name}'s monthly burn rate?",
        "How much does {name} spend per month?",
        "What is the burn rate for {name}?",
    ],
    "scope_change_pct": [
        "What is {name}'s scope change percentage?",
        "How much has {name}'s scope changed?",
        "What percentage of scope change has {name} experienced?",
    ],
    "velocity_points": [
        "What is {name}'s sprint velocity?",
        "How many story points does {name} complete per sprint?",
        "What velocity does {name} maintain?",
    ],
    "risk_score": [
        "What is {name}'s risk score?",
        "How does {name} rate on the risk scale?",
        "What risk score has been assigned to {name}?",
    ],
    "budget_variance_pct": [
        "What is {name}'s budget variance?",
        "How much is {name} over or under budget?",
        "What budget variance percentage does {name} show?",
    ],
    "project_description": [
        "What does {name} do?",
        "Describe {name}'s purpose.",
        "What is {name} about?",
    ],
    "key_risk": [
        "What is {name}'s key risk?",
        "What is the primary risk for {name}?",
        "Describe the main risk facing {name}.",
    ],
    "status": [
        "What is {name}'s current status?",
        "What status is {name} in?",
        "What phase is {name} currently in?",
    ],
    "priority": [
        "What is {name}'s priority level?",
        "What priority has been assigned to {name}?",
        "How is {name} prioritized?",
    ],
    "start_date": [
        "When did {name} start?",
        "What is {name}'s start date?",
        "When was {name} kicked off?",
    ],
    "deadline": [
        "When is {name}'s deadline?",
        "What is the due date for {name}?",
        "When is {name} expected to be completed?",
    ],
    "weekly_velocity": [
        "What are {name}'s weekly sprint velocity figures?",
        "List {name}'s velocity for the last 4 weeks.",
        "What is {name}'s weekly velocity breakdown?",
    ],
    "monthly_burn": [
        "What are {name}'s monthly burn figures?",
        "List {name}'s spending for the last 5 months.",
        "What is {name}'s month-by-month burn rate?",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "team_size": [
        ("has a team of {val} members", "none"),
        ("team size figures of {val} and {distractor} across restructurings",
         "temporal"),
        ("team counts of {distractor} and {val} by different org charts",
         "qualified"),
    ],
    "milestone_count": [
        ("has {val} milestones defined in its roadmap", "none"),
        ("milestone counts of {val} and {distractor} in different plans",
         "temporal"),
        ("with {distractor} and {val} milestones in separate trackers",
         "comparative"),
    ],
    "task_backlog": [
        ("currently has {val} items in its task backlog", "none"),
        ("backlog counts of {val} and {distractor} across sprints",
         "temporal"),
        ("backlog tallies of {distractor} and {val} by different filters",
         "qualified"),
    ],
    "closed_issues": [
        ("has resolved {val} issues to date", "none"),
        ("closed issue counts of {distractor} and {val} in successive periods",
         "temporal"),
        ("with {val} and {other_val} closed issues in separate tallies",
         "comparative"),
    ],
    "sprint_count": [
        ("has completed {val} sprints so far", "none"),
        ("sprint counts of {val} and {distractor} in different tracking systems",
         "temporal"),
    ],
    "dependency_count": [
        ("relies on {val} external dependencies", "none"),
        ("dependency counts of {distractor} and {val} in different audits",
         "temporal"),
    ],
    "stakeholder_count": [
        ("involves {val} stakeholders in its governance", "none"),
        ("stakeholder counts of {val} and {distractor} across reorganizations",
         "temporal"),
    ],
    "release_count": [
        ("has shipped {val} releases to production", "none"),
        ("release counts of {val} and {distractor} in different registries",
         "temporal"),
    ],
    "completion_pct": [
        ("is {val} complete", "none"),
        ("completion readings of {val} and {distractor} in different reports",
         "temporal"),
        ("completion estimates of {distractor} and {val} by different methods",
         "qualified"),
    ],
    "budget_k": [
        ("has an allocated budget of {val}", "none"),
        ("budget figures of {val} and {distractor} across revisions",
         "temporal"),
        ("budget estimates of {other_val} and {val} from different approvals",
         "comparative"),
    ],
    "burn_rate_k": [
        ("is spending at a rate of {val} per month", "none"),
        ("burn rate readings of {distractor} and {val} across quarters",
         "temporal"),
        ("spending rates of {val} and {other_val} in different calculations",
         "comparative"),
    ],
    "scope_change_pct": [
        ("has experienced {val} scope change since kickoff", "none"),
        ("scope change readings of {val} and {distractor} across reviews",
         "temporal"),
        ("scope change estimates of {distractor} and {val} by different methods",
         "qualified"),
    ],
    "velocity_points": [
        ("delivers {val} story points per sprint", "none"),
        ("velocity readings of {distractor} and {val} in successive sprints",
         "temporal"),
        ("velocity estimates of {val} and {other_val} from different methods",
         "comparative"),
    ],
    "risk_score": [
        ("carries a risk score of {val}", "none"),
        ("risk scores of {val} and {distractor} in different assessments",
         "temporal"),
        ("risk ratings of {distractor} and {val} under different frameworks",
         "qualified"),
    ],
    "budget_variance_pct": [
        ("shows a budget variance of {val}", "none"),
        ("budget variance readings of {distractor} and {val} across periods",
         "temporal"),
        ("variance estimates of {val} and {other_val} from different reports",
         "comparative"),
    ],
    "project_description": [
        ("{val}", "none"),
    ],
    "key_risk": [
        ("{val}", "none"),
    ],
    "status": [
        ("is currently in {val} status", "none"),
    ],
    "priority": [
        ("has been assigned {val} priority", "none"),
    ],
    "start_date": [
        ("was kicked off on {val}", "none"),
    ],
    "deadline": [
        ("has a deadline of {val}", "none"),
    ],
    "weekly_velocity": [
        ("recorded weekly velocities of {val}", "none"),
    ],
    "monthly_burn": [
        ("reported monthly spending of {val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("closed_issues", "task_backlog", "closed-to-backlog issue ratio"),
    ("budget_k", "team_size", "budget per team member in $K"),
    ("closed_issues", "sprint_count", "issues closed per sprint"),
    ("burn_rate_k", "team_size", "burn rate per team member in $K/mo"),
    ("task_backlog", "team_size", "backlog items per team member"),
    ("velocity_points", "team_size", "velocity per team member"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr == "budget_k":
        return f"${val:,.1f}K" if isinstance(val, (int, float)) else str(val)
    if attr == "burn_rate_k":
        return f"${val:,.1f}K/mo" if isinstance(val, (int, float)) else str(val)
    if attr in ("completion_pct", "scope_change_pct", "budget_variance_pct"):
        return f"{val:.1f}%" if isinstance(val, (int, float)) else str(val)
    if attr in ("task_backlog", "closed_issues"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr in ("weekly_velocity", "monthly_burn") and isinstance(val, list):
        if attr == "monthly_burn":
            return ", ".join(f"${v:,.1f}K" for v in val)
        return ", ".join(f"{v:.1f}" for v in val)
    if attr == "risk_score":
        return f"{val:.1f}" if isinstance(val, (int, float)) else str(val)
    if attr == "velocity_points":
        return f"{val:.1f}" if isinstance(val, (int, float)) else str(val)
    return str(val)


class ProjectWorld(WorldTemplate):
    """Project management — 600 names × 23 attrs × 12 methodologies."""

    @property
    def name(self) -> str:
        return "project"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_METHODOLOGIES)

    @property
    def entity_word(self) -> str:
        return "project"

    @property
    def correction_rate(self) -> float:
        return 0.10  # moderate — scope/schedule changes

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.4, 0.7)  # standard timing

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.30,
            "comprehension": 0.35,   # ratio/comparison/aggregation emphasis
            "update": 0.20,
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(p, s) for p in _PREFIXES for s in _SUFFIXES]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{p} {s}" for p, s in selected]

    def _generate_list_float(self, adef, rng):
        """Pattern varies by attribute."""
        if adef.name == "monthly_burn":
            # S-curve: ramp up, peak mid-project, taper off
            peak = rng.uniform(adef.min_val * 0.5, adef.max_val * 0.6)
            values = []
            for i in range(adef.list_len):
                t = (i + 0.5) / adef.list_len  # 0.1..0.9
                mult = 4 * t * (1 - t)  # parabolic, peaks at t=0.5
                noise = rng.uniform(0.85, 1.15)
                val = max(adef.min_val, min(adef.max_val,
                                            peak * mult * noise))
                values.append(round(val, 2))
            return values
        # weekly_velocity: ramp-up pattern
        base = rng.uniform(adef.min_val * 0.5, adef.max_val * 0.4)
        ramp = [0.60, 0.80, 1.00, 1.10]  # W1-W4: team ramps up over weeks
        values = []
        for i in range(adef.list_len):
            mult = ramp[i % 4]
            noise = rng.uniform(0.90, 1.10)
            val = max(adef.min_val, min(adef.max_val, base * mult * noise))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)
        # Constraint 1: burn_rate should be realistic given budget
        if "burn_rate_k" in attrs and "budget_k" in attrs:
            budget = attrs["budget_k"]
            burn = attrs["burn_rate_k"]
            if burn * 12 > budget * 3:
                attrs["burn_rate_k"] = round(
                    rng.uniform(budget * 0.02, budget * 0.15), 2)
        # Constraint 2: task_backlog + closed_issues should be realistic
        if "task_backlog" in attrs and "closed_issues" in attrs:
            total = attrs["task_backlog"] + attrs["closed_issues"]
            if total < 20:
                attrs["closed_issues"] = rng.randint(20, 500)
        # Constraint 3: completion_pct correlates with closed/(closed+backlog)
        if ("completion_pct" in attrs and "closed_issues" in attrs
                and "task_backlog" in attrs):
            closed = attrs["closed_issues"]
            backlog = attrs["task_backlog"]
            total = closed + backlog
            if total > 0:
                implied = (closed / total) * 100
                # Blend: 60% implied, 40% random (adds noise but keeps correlation)
                attrs["completion_pct"] = round(
                    implied * 0.6 + attrs["completion_pct"] * 0.4, 2)
                attrs["completion_pct"] = max(0, min(100,
                                                     attrs["completion_pct"]))
        # Constraint 4: completed projects have high completion, low backlog
        if "status" in attrs and attrs["status"] == "completed":
            if "completion_pct" in attrs:
                attrs["completion_pct"] = round(
                    rng.uniform(95, 100), 2)
            if "task_backlog" in attrs:
                attrs["task_backlog"] = rng.randint(0, 5)
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
            ("shares_team_with", "shares team members with", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "depends_on":
            return (f"{rel.source} depends on {rel.target} for critical "
                    f"deliverables in its integration roadmap.")
        if rel.relation == "shares_team_with":
            return (f"{rel.source} and {rel.target} share team members "
                    f"who split time between both projects.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
        style = rng.choice(["report", "narrative", "bulletin", "memo"])
        header = {
            "report": (f"PROJECT STATUS REPORT — {entity.name}\n"
                       f"Methodology: {entity.category}\n"),
            "narrative": (f"PROJECT REVIEW — {entity.name}\n"
                          f"Approach: {entity.category}\n"),
            "bulletin": (f"PROJECT BULLETIN — {entity.name}\n"
                         f"Framework: {entity.category}\n"),
            "memo": (f"PROJECT MEMO — {entity.name}\n"
                     f"Process: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION NOTICE: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following a project review."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
