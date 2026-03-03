"""Domain implementations for MemoryBench."""

from memorybench.domains.base import Distractor, Domain, Entity, QA, Task, TaskResult
from memorybench.domains.logistics import LogisticsDomain
from memorybench.domains.organization import OrgDomain
from memorybench.domains.research import ResearchDomain

ALL_DOMAINS = [OrgDomain(), ResearchDomain(), LogisticsDomain()]

__all__ = [
    "Distractor", "Domain", "Entity", "QA", "Task", "TaskResult",
    "OrgDomain", "ResearchDomain", "LogisticsDomain",
    "ALL_DOMAINS",
]
