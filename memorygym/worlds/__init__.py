"""World templates for MemoryGym."""

from memorygym.worlds.base import WorldTemplate, World, EntitySpec, GeneratedQA, Correction
from memorygym.worlds.company import CompanyWorld
from memorygym.worlds.research import ResearchWorld
from memorygym.worlds.city import CityWorld
from memorygym.worlds.hospital import HospitalWorld
from memorygym.worlds.sport import SportWorld

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
