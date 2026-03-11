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

ALL_TEMPLATES: dict[str, type[WorldTemplate]] = {
    "company": CompanyWorld,
    "research": ResearchWorld,
    "city": CityWorld,
    "hospital": HospitalWorld,
    "sport": SportWorld,
    "movie": MovieWorld,
    "university": UniversityWorld,
    "codebase": CodebaseWorld,
}

__all__ = [
    "WorldTemplate", "World", "EntitySpec", "GeneratedQA", "Correction", "Contradiction", "Relationship",
    "CompanyWorld", "ResearchWorld", "CityWorld", "HospitalWorld", "SportWorld",
    "MovieWorld", "UniversityWorld", "CodebaseWorld", "ALL_TEMPLATES",
]
