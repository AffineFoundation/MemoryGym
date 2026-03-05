"""World templates for MemoryBench."""

from memorybench.worlds.base import WorldTemplate, World, EntitySpec, GeneratedQA, Correction
from memorybench.worlds.company import CompanyWorld
from memorybench.worlds.research import ResearchWorld
from memorybench.worlds.city import CityWorld
from memorybench.worlds.hospital import HospitalWorld
from memorybench.worlds.sport import SportWorld

ALL_TEMPLATES: dict[str, type[WorldTemplate]] = {
    "company": CompanyWorld,
    "research": ResearchWorld,
    "city": CityWorld,
    "hospital": HospitalWorld,
    "sport": SportWorld,
}

__all__ = [
    "WorldTemplate", "World", "EntitySpec", "GeneratedQA", "Correction",
    "CompanyWorld", "ResearchWorld", "CityWorld", "HospitalWorld", "SportWorld",
    "ALL_TEMPLATES",
]
