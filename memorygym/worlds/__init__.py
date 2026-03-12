"""World templates for MemoryGym."""

from .base import WorldTemplate, World, EntitySpec, GeneratedQA, Correction, Contradiction, Relationship
from .company import CompanyWorld
from .research import ResearchWorld
from .city import CityWorld
from .hospital import HospitalWorld
from .sport import SportWorld
from .movie import MovieWorld
from .university import UniversityWorld
from .codebase import CodebaseWorld
from .project import ProjectWorld
from .agentteam import AgentteamWorld

ALL_TEMPLATES: dict[str, type[WorldTemplate]] = {
    "company": CompanyWorld,
    "research": ResearchWorld,
    "city": CityWorld,
    "hospital": HospitalWorld,
    "sport": SportWorld,
    "movie": MovieWorld,
    "university": UniversityWorld,
    "codebase": CodebaseWorld,
    "project": ProjectWorld,
    "agentteam": AgentteamWorld,
}

# Stable registry: index → template name.
# Only append — never reorder or remove existing entries.
# This is the stability contract for task_id mapping.
TEMPLATE_REGISTRY: list[str] = [
    "company",      # 0
    "research",     # 1
    "city",         # 2
    "hospital",     # 3
    "sport",        # 4
    "movie",        # 5
    "university",   # 6
    "codebase",     # 7
    "project",      # 8
    "agentteam",    # 9
]

assert all(t in ALL_TEMPLATES for t in TEMPLATE_REGISTRY), (
    f"TEMPLATE_REGISTRY has entries not in ALL_TEMPLATES: "
    f"{[t for t in TEMPLATE_REGISTRY if t not in ALL_TEMPLATES]}"
)

__all__ = [
    "WorldTemplate", "World", "EntitySpec", "GeneratedQA", "Correction", "Contradiction", "Relationship",
    "CompanyWorld", "ResearchWorld", "CityWorld", "HospitalWorld", "SportWorld",
    "MovieWorld", "UniversityWorld", "CodebaseWorld", "ProjectWorld", "AgentteamWorld",
    "ALL_TEMPLATES", "TEMPLATE_REGISTRY",
]
