"""Combinatorial name pools for anti-memorization.

Person names: 36×20=720 firsts × 35×20=700 lasts = 504,000 combinations.
Product names: (30×18)×50 = 27,000 combinations.
"""

from __future__ import annotations

import random

# ── Person name syllable components ──

FIRST_PARTS_A = [
    "Kel", "Tor", "Val", "Bri", "Ren", "Ash", "Cal", "Dor", "Eil",
    "Fen", "Gar", "Hal", "Ira", "Jov", "Kir", "Lan", "Mar", "Nor",
    "Ori", "Pel", "Rae", "Sol", "Tal", "Ula", "Vin", "Wen", "Xan",
    "Zev", "Arn", "Bel", "Cor", "Del", "Eth", "Fal", "Gil", "Hes",
]

FIRST_PARTS_B = [
    "an", "en", "is", "or", "us", "ia", "el", "on", "ar", "in",
    "os", "id", "ax", "ir", "um", "ek", "ith", "yn", "al", "es",
]

LAST_PARTS_A = [
    "Brant", "Crest", "Dorn", "Frost", "Gale", "Hart", "Kell",
    "Lark", "Moor", "Nord", "Pike", "Rend", "Stone", "Thorn",
    "Vale", "Ward", "Wren", "Ash", "Brook", "Cross", "Drake",
    "Fell", "Grove", "Hale", "Kirk", "Marsh", "Rath", "Stern",
    "Voss", "Birch", "Cairn", "Fenn", "Holt", "Knoll", "Ridge",
]

LAST_PARTS_B = [
    "wick", "wood", "ford", "ley", "ton", "field", "burg", "dale",
    "shire", "croft", "worth", "well", "gate", "holm", "stead",
    "mere", "haven", "fell", "borne", "brook",
]

# ── Product name components (combinatorial: 30×18×50 = 27,000) ──

PRODUCT_PARTS_A = [
    "Apex", "Brace", "Core", "Delta", "Echo", "Flux", "Grid",
    "Helix", "Ion", "Jet", "Kilo", "Lynx", "Micro", "Nano",
    "Omega", "Pulse", "Quad", "Relay", "Sigma", "Turbo",
    "Ultra", "Vector", "Wave", "Xray", "Yoke", "Zenith",
    "Alpha", "Beta", "Gamma", "Lambda",
]

PRODUCT_PARTS_B = [
    "-X", "-Z", "-V", "-Q", "-R", "-S", "-T", "-N",
    "-Pro", "-Max", "-Neo", "-Gen", "-Mk2", "-Plus",
    "-Lite", "-Arc", "-Ion", "-Prime",
]

PRODUCT_SUFFIXES = [
    "Controller", "Actuator", "Module", "Sensor", "Transmitter",
    "Capacitor", "Inverter", "Rotor", "Stabilizer", "Compressor",
    "Adapter", "Monitor", "Regulator", "Filter", "Converter",
    "Generator", "Amplifier", "Switch", "Valve", "Encoder",
    "Coupler", "Drive", "Modulator", "Scanner", "Connector",
    "Processor", "Resistor", "Conduit", "Oscillator", "Inductor",
    "Unit", "Hub", "Node", "Link", "Cell",
    "Probe", "Array", "Matrix", "Beacon", "Nexus",
    "Forge", "Vault", "Stack", "Lattice", "Circuit",
    "Bridge", "Frame", "Chamber", "Coil", "Lens",
]


class NamePool:
    """Generates unique combinatorial names from two component lists.

    Each name = choice(parts_a) + choice(parts_b).
    For person names: first = FIRST_A+FIRST_B, last = LAST_A+LAST_B.
    For product names: prefix + " " + suffix.
    """

    def __init__(self, rng: random.Random, count: int,
                 first_a: list[str], first_b: list[str],
                 last_a: list[str], last_b: list[str],
                 separator: str = " "):
        self._names: list[str] = []
        seen: set[str] = set()
        attempts = 0
        while len(self._names) < count:
            first = rng.choice(first_a) + rng.choice(first_b)
            last = rng.choice(last_a) + rng.choice(last_b)
            full = f"{first}{separator}{last}"
            if full.lower() not in seen:
                seen.add(full.lower())
                self._names.append(full)
            attempts += 1
            if attempts > count * 50:
                raise RuntimeError(f"Cannot generate {count} unique names")
        self._idx = 0

    def pop(self) -> str:
        name = self._names[self._idx]
        self._idx += 1
        return name


def person_name_pool(rng: random.Random, count: int) -> NamePool:
    """Create a pool of combinatorial person names (504K possible)."""
    return NamePool(rng, count,
                    FIRST_PARTS_A, FIRST_PARTS_B,
                    LAST_PARTS_A, LAST_PARTS_B)


def product_name_pool(rng: random.Random, count: int) -> NamePool:
    """Create a pool of combinatorial product names (27K possible)."""
    return NamePool(rng, count,
                    PRODUCT_PARTS_A, PRODUCT_PARTS_B,
                    PRODUCT_SUFFIXES, [""],
                    separator=" ")
