"""Logistics domain: products, inventory, supply chain metrics."""

from __future__ import annotations

import random

from memorybench.domains.base import Distractor, Domain, Entity
from memorybench.domains.names import product_name_pool

SKU_PREFIXES = ["WDG", "CMP", "ELX", "MFG", "PKG"]

ORDER_STATUSES = ["pending", "shipped", "delivered", "backordered", "cancelled"]
SUPPLIERS = [
    "Northgate Supply", "Eastern Components", "Pacific Parts",
    "Continental Logistics", "Meridian Distribution",
]

CATEGORIES = [
    "Electronics", "Mechanical", "Hydraulic", "Thermal", "Optical",
]

REGIONS = ["North", "South", "East", "West", "Central"]


class LogisticsDomain(Domain):
    name = "logistics"
    ALL_ATTRS = ["unit_price", "weight_kg", "lead_time_days",
                 "defect_rate", "demand_forecast", "stock_level"]
    SYNTHESIS_ENTITY_WORD = "product"
    GROUP_NAMES = CATEGORIES
    ATTR_SYNONYMS = {
        "unit_price": {"unit_price", "price", "costs", "priced at", "$",
                       "unit_price=", "cost per unit", "per-unit cost"},
        "weight_kg": {"weight_kg", "weight", "weighs", "kg", "kilograms",
                      "weight_kg=", "weigh", "heavy"},
        "lead_time_days": {"lead_time_days", "lead time", "delivery",
                           "days to deliver", "lead_time_days=",
                           "deliver", "arrive"},
        "defect_rate": {"defect_rate", "defect rate", "failure rate",
                        "defect", "defect_rate=", "defective"},
        "demand_forecast": {"demand_forecast", "demand", "forecast",
                            "projected demand", "demand_forecast=",
                            "projected"},
        "stock_level": {"stock_level", "stock", "inventory", "units in stock",
                        "stock_level="},
    }
    DOC_TEMPLATES = [
        "Product {name} (SKU: {sku}) in the {group} category — {details}.",
        "Inventory record for {name} ({sku}), classified as {group}. "
        "{details}.",
        "The {group} line includes {name} (SKU: {sku}), which {details}.",
    ]
    BACKGROUND = [
        "Supply chain optimization efforts have led to revised inventory "
        "policies across all regional warehouses.",
        "Quality assurance protocols now require more frequent sampling and "
        "testing of incoming shipments.",
        "Logistics planning tools are being upgraded to incorporate real-time "
        "demand forecasting capabilities.",
    ]

    def generate_kb(self, seed, n_entities=20):
        rng = random.Random(seed)
        active, primary = self._select_schema(seed)
        pool = product_name_pool(rng, n_entities)
        entities = []
        for _ in range(n_entities):
            prefix = rng.choice(SKU_PREFIXES)
            sku = f"{prefix}-{rng.randint(1000, 9999)}"
            attrs = {"_sku": sku}
            if "unit_price" in active:
                attrs["unit_price"] = round(rng.uniform(5, 500), 2)
            if "weight_kg" in active:
                attrs["weight_kg"] = round(rng.uniform(0.1, 50), 1)
            if "lead_time_days" in active:
                attrs["lead_time_days"] = rng.randint(1, 60)
            if "defect_rate" in active:
                attrs["defect_rate"] = round(rng.uniform(0.1, 8.0), 2)
            if "demand_forecast" in active:
                attrs["demand_forecast"] = rng.randint(50, 5000)
            if "stock_level" in active:
                attrs["stock_level"] = rng.randint(0, 2000)
            entities.append(Entity(pool.pop(), rng.choice(self.GROUP_NAMES), attrs))
        rng.shuffle(entities)
        return {"entities": entities, "active_attrs": active,
                "primary_attr": primary}

    def _render_details(self, e, active_attrs):
        parts = []
        a = e.attrs
        if "unit_price" in active_attrs and a.get("unit_price"):
            parts.append(f"is priced at ${a['unit_price']:.2f} per unit")
        if "weight_kg" in active_attrs and a.get("weight_kg"):
            parts.append(f"weighs {a['weight_kg']} kg")
        if "lead_time_days" in active_attrs and a.get("lead_time_days"):
            parts.append(f"has a lead time of {a['lead_time_days']} days")
        if "defect_rate" in active_attrs and a.get("defect_rate"):
            parts.append(f"has a defect rate of {a['defect_rate']}%")
        if "demand_forecast" in active_attrs and a.get("demand_forecast"):
            parts.append(f"has projected demand of {a['demand_forecast']} units")
        if "stock_level" in active_attrs and a.get("stock_level"):
            parts.append(f"has {a['stock_level']} units in stock")
        return self._render_detail_list(parts) or "is a standard component"

    def render_entity_doc(self, entity, active_attrs, rng):
        tmpl = rng.choice(self.DOC_TEMPLATES)
        return tmpl.format(
            name=entity.name, sku=entity.attrs.get("_sku", "N/A"),
            group=entity.group,
            details=self._render_details(entity, active_attrs),
        )

    def render_correction(self, entity, attr, old_val, new_val):
        labels = {
            "unit_price": f"price corrected from ${old_val:.2f} to ${new_val:.2f}",
            "weight_kg": f"weight corrected from {old_val} to {new_val} kg",
            "lead_time_days": f"lead time updated from {old_val} to {new_val} days",
            "defect_rate": f"defect rate corrected from {old_val}% to {new_val}%",
            "demand_forecast": f"demand forecast updated from {old_val} to {new_val}",
            "stock_level": f"stock level corrected from {old_val} to {new_val}",
        }
        detail = labels.get(attr, f"{attr} changed from {old_val} to {new_val}")
        return f"CORRECTION NOTICE: {entity.name}'s {detail} per latest audit."

    def generate_distractors(self, rng, entities, n=10):
        distractors = []
        for _ in range(min(n, len(entities))):
            product = rng.choice(entities)
            if rng.random() < 0.5:
                text = (
                    f"Supply Order #{rng.randint(10000,99999)}\n"
                    f"  Product: {product.name} | "
                    f"Supplier: {rng.choice(SUPPLIERS)}\n"
                    f"  Quantity: {rng.randint(10,500)} units | "
                    f"Status: {rng.choice(ORDER_STATUSES)}\n"
                    f"  Estimated arrival: 2024-{rng.randint(1,12):02d}-"
                    f"{rng.randint(1,28):02d}"
                )
            else:
                text = (
                    f"Shipment Notice: {product.group} batch\n"
                    f"  Contains: {product.name} and related items\n"
                    f"  Origin: {rng.choice(REGIONS)} warehouse\n"
                    f"  Destination: {rng.choice(REGIONS)} distribution center\n"
                    f"  Pallets: {rng.randint(1,20)}"
                )
            distractors.append(Distractor(text))
        return distractors

    def _q_text(self, attr, name, rng=None):
        phrasings = {
            "unit_price": [
                f"What is the unit price of {name}?",
                f"How much does {name} cost per unit?",
                f"Tell me the per-unit cost of {name}.",
                f"What is {name} priced at?",
                f"Report the unit price for {name}.",
            ],
            "weight_kg": [
                f"How much does {name} weigh?",
                f"What is the weight of {name} in kilograms?",
                f"Tell me {name}'s weight in kg.",
                f"What does {name} weigh?",
                f"How heavy is {name}?",
            ],
            "lead_time_days": [
                f"What is the lead time for {name}?",
                f"How many days does it take to deliver {name}?",
                f"What is {name}'s delivery lead time in days?",
                f"How long does {name} take to arrive?",
                f"Tell me the lead time for {name} in days.",
            ],
            "defect_rate": [
                f"What is the defect rate of {name}?",
                f"What percentage of {name} units are defective?",
                f"Tell me {name}'s failure rate.",
                f"How high is the defect rate for {name}?",
                f"What is the defect percentage for {name}?",
            ],
            "demand_forecast": [
                f"What is the demand forecast for {name}?",
                f"How many units of {name} are projected to be needed?",
                f"What is the projected demand for {name}?",
                f"Tell me {name}'s demand forecast figure.",
                f"How many units of {name} does the forecast predict?",
            ],
            "stock_level": [
                f"How many units of {name} are in stock?",
                f"What is the current inventory level of {name}?",
                f"Tell me how much {name} is currently in stock.",
                f"What is {name}'s stock level?",
                f"How many units of {name} remain in inventory?",
            ],
        }
        opts = phrasings[attr]
        return rng.choice(opts) if rng else opts[0]

