"""Data types for MemoryGym world templates.

Extracted to avoid circular imports between base.py and questions.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AttrDef:
    """Attribute schema definition.

    Supported dtypes:
    - "int", "float": numeric (uses min_val/max_val)
    - "text": free-form text (uses text_pool for generation)
    - "enum": categorical (uses choices)
    - "list_float": numeric sequence (uses min_val/max_val, list_len)
    - "date": date string "YYYY-MM-DD" (uses min_val/max_val as year range)
    """

    name: str
    dtype: str       # "int", "float", "text", "enum", "list_float", "date"
    min_val: float = 0.0
    max_val: float = 100.0
    unit: str = ""   # "$M", "%", etc.
    label: str = ""  # human-readable; defaults to name
    agg_ops: tuple[str, ...] = ("total", "average")  # valid aggregation ops
    # For "enum" dtype:
    choices: list[str] = field(default_factory=list)
    # For "list_float" dtype:
    list_len: int = 5
    # For "text" dtype: pool of sentence fragments to compose from
    text_pool: list[str] = field(default_factory=list)


@dataclass
class EntitySpec:
    """A generated entity with typed attributes."""

    name: str
    category: str
    attrs: dict[str, Any] = field(default_factory=dict)
    parent: str | None = None  # hierarchical parent entity name
    children: list[str] = field(default_factory=list)

    def get(self, attr: str, default=None):
        return self.attrs.get(attr, default)


@dataclass
class GeneratedQA:
    """A question with computable ground truth."""

    question: str
    answer: str
    competency: str
    required_entities: list[str] = field(default_factory=list)
    purpose: str = ""  # "recall", "coverage", "comprehension", "update", ...
    source_attr: str = ""  # attribute name the question targets


@dataclass
class SentenceTemplate:
    """Narrative sentence template embedding an attribute value with distractors."""

    template: str       # Format string: {val}, {distractor}, {other_name}, {other_val}
    attr: str           # Primary attribute name
    distractor: str     # "temporal" | "comparative" | "qualified" | "none"


@dataclass
class Correction:
    """A correction event that mutates world state."""

    entity_name: str
    attr: str
    old_val: Any
    new_val: Any
    notice: str  # rendered correction document


@dataclass
class Contradiction:
    """An implicit contradiction — updated value without explicit notice.

    Unlike Correction (which has a "CORRECTION NOTICE" label), a
    contradiction arrives as a normal document with a different value.
    The agent must detect the discrepancy and update its memory.
    """

    entity_name: str
    attr: str
    old_val: Any
    new_val: Any
    document: str  # rendered as a normal document (no CORRECTION label)


@dataclass
class Relationship:
    """A directed relationship between two entities."""

    source: str       # source entity name
    relation: str     # relationship type (e.g. "supplies_to")
    target: str       # target entity name


@dataclass
class World:
    """Complete deterministic world state from one seed."""

    entities: list[EntitySpec]
    attr_defs: list[AttrDef]
    active_attrs: list[str]
    categories: list[str]
    seed: int
    relationships: list[Relationship] = field(default_factory=list)

    def get_entity(self, name: str) -> EntitySpec | None:
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relationships(self, name: str) -> list[Relationship]:
        """Get all relationships involving an entity (as source or target)."""
        return [r for r in self.relationships
                if r.source == name or r.target == name]

    def get_outgoing(self, name: str) -> list[Relationship]:
        """Get relationships where entity is the source."""
        return [r for r in self.relationships if r.source == name]

    def get_incoming(self, name: str) -> list[Relationship]:
        """Get relationships where entity is the target."""
        return [r for r in self.relationships if r.target == name]

    def entities_in_category(self, cat: str) -> list[EntitySpec]:
        return [e for e in self.entities if e.category == cat]
