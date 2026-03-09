"""World templates for MemoryGym."""

from memorygym.worlds.base import WorldTemplate, World, EntitySpec, GeneratedQA, Correction, Contradiction, Relationship
from memorygym.worlds.company import CompanyWorld
from memorygym.worlds.research import ResearchWorld
from memorygym.worlds.city import CityWorld
from memorygym.worlds.hospital import HospitalWorld
from memorygym.worlds.sport import SportWorld
from memorygym.worlds.movie import MovieWorld

ALL_TEMPLATES: dict[str, type[WorldTemplate]] = {
    "company": CompanyWorld,
    "research": ResearchWorld,
    "city": CityWorld,
    "hospital": HospitalWorld,
    "sport": SportWorld,
    "movie": MovieWorld,
}

__all__ = [
    "WorldTemplate", "World", "EntitySpec", "GeneratedQA", "Correction", "Contradiction", "Relationship",
    "CompanyWorld", "ResearchWorld", "CityWorld", "HospitalWorld", "SportWorld",
    "MovieWorld", "ALL_TEMPLATES",
]
