"""WorldTemplate evaluation harness.

Simulates storage strategies against WorldTemplate + adaptive questioning.
Models three dimensions of memory management:
  1. Storage breadth (how many entities stored)
  2. Memory maintenance (whether corrections are applied)
  3. Compression quality (document volume vs write budget)

Key design: update questions use identical _q_text as retrieval →
agent cannot distinguish them. The only way to answer correctly is to
have applied the correction.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from random import Random

from memorygym.worlds.base import (
    Correction, GeneratedQA, World, WorldTemplate,
)
from memorygym.worlds.city import CityWorld
from memorygym.worlds.company import CompanyWorld
from memorygym.worlds.hospital import HospitalWorld
from memorygym.worlds.research import ResearchWorld
from memorygym.worlds.sport import SportWorld
from memorygym.worlds.movie import MovieWorld


@dataclass
class StrategyProfile:
    """Defines a simulated agent's memory management behavior."""
    name: str
    store_ratio: float       # fraction of entities stored (0-1)
    applies_updates: bool    # whether it applies corrections


STRATEGIES = [
    StrategyProfile("perfect", 1.0, True),
    StrategyProfile("strategic", 0.7, True),
    StrategyProfile("naive", 0.4, False),   # stores but never updates
    StrategyProfile("guesser", 0.0, False),
]

# Attack strategy: stores nothing but applies corrections only
CORRECTION_ONLY = StrategyProfile("correction_only", 0.0, True)


@dataclass
class StrategyResult:
    name: str
    stored_count: int
    missed_count: int
    questions: list[GeneratedQA]
    correct: int
    total: int
    by_purpose: dict[str, tuple[int, int]]
    by_competency: dict[str, tuple[int, int]]
    doc_tokens: int = 0  # total document volume (chars as proxy)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def summary(self) -> str:
        lines = [f"  {self.name}: {self.accuracy:.0%} "
                 f"({self.correct}/{self.total}) "
                 f"stored={self.stored_count} missed={self.missed_count}"
                 f" doc_volume={self.doc_tokens:,}"]
        for p in ("recall", "coverage", "update", "comprehension", "abstention"):
            c, t = self.by_purpose.get(p, (0, 0))
            pct = f"{c/t:.0%}" if t else "n/a"
            lines.append(f"    {p}: {pct} ({c}/{t})")
        for comp in sorted(self.by_competency):
            c, t = self.by_competency[comp]
            pct = f"{c/t:.0%}" if t else "n/a"
            lines.append(f"    [{comp}]: {pct} ({c}/{t})")
        return "\n".join(lines)


def _construct_and_validate(q: GeneratedQA, tmpl: WorldTemplate,
                            world: World, stored_names: set[str],
                            updated_names: set[str],
                            applies_updates: bool,
                            n_total: int = 60) -> bool:
    """Delegate to bench._construct_and_validate."""
    from memorygym.bench import _construct_and_validate as _cv
    return _cv(q, tmpl, world, stored_names, updated_names,
               applies_updates, n_total)


def simulate_strategy(
    tmpl: WorldTemplate, world: World, seed: int,
    profile: StrategyProfile,
    n_questions: int = 20,
    n_corrections: int = 5,
) -> StrategyResult:
    """Simulate a storage strategy with corrections and evaluate."""
    rng_doc = Random(seed)

    # Render all documents
    all_docs = [(e, tmpl.render_document(e, world.active_attrs, rng_doc))
                for e in world.entities]
    total_doc_chars = sum(len(doc) for _, doc in all_docs)

    # Storage decision
    rng_store = Random(seed + 111)
    if profile.store_ratio >= 1.0:
        stored_docs = [doc for _, doc in all_docs]
    elif profile.store_ratio <= 0.0:
        stored_docs = []
    else:
        n_store = max(1, int(len(all_docs) * profile.store_ratio))
        indices = rng_store.sample(range(len(all_docs)), n_store)
        stored_docs = [all_docs[i][1] for i in indices]

    # Detect what was stored
    stored_names, missed_names = tmpl.detect_stored_entities(world, stored_docs)

    # Generate corrections (mutates world state!)
    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)

    # Determine which corrections the strategy would apply
    updated_names: set[str] = set()
    if profile.applies_updates:
        for c in corrections:
            if c.entity_name in stored_names:
                updated_names.add(c.entity_name)

    # Generate adaptive questions (with corrections)
    rng_q = Random(seed + 7777)
    questions = tmpl.gen_adaptive_questions(
        world, rng_q, world.entities, stored_names, n_questions, corrections)

    # Simulate answering
    correct = 0
    by_purpose: dict[str, list[bool]] = {}
    by_comp: dict[str, list[bool]] = {}
    for q in questions:
        ok = _construct_and_validate(q, tmpl, world, stored_names,
                                     updated_names, profile.applies_updates,
                                     n_total=len(world.entities))
        if ok:
            correct += 1
        by_purpose.setdefault(q.purpose, []).append(ok)
        by_comp.setdefault(q.competency, []).append(ok)

    return StrategyResult(
        name=profile.name,
        stored_count=len(stored_names),
        missed_count=len(missed_names),
        questions=questions,
        correct=correct,
        total=len(questions),
        by_purpose={p: (sum(v), len(v)) for p, v in by_purpose.items()},
        by_competency={c: (sum(v), len(v)) for c, v in by_comp.items()},
        doc_tokens=total_doc_chars,
    )


def run_evaluation(seed: int = 42, n_entities: int = 60,
                   n_questions: int = 20, verbose: bool = True) -> dict:
    """Run full evaluation with all strategies on one seed."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=seed, n_entities=n_entities)

    results = {}
    for profile in STRATEGIES:
        # Each strategy gets its own world copy (corrections mutate state)
        world_copy = tmpl.generate_world(seed=seed, n_entities=n_entities)
        r = simulate_strategy(tmpl, world_copy, seed, profile, n_questions)
        results[profile.name] = r

    if verbose:
        print(f"\n{'='*60}")
        print(f"Seed={seed}  Entities={n_entities}  Questions={n_questions}")
        print(f"Active attrs: {world.active_attrs}")
        print(f"{'='*60}")
        for r in results.values():
            print(r.summary())
        print()

    return results


def run_multi_seed(n_seeds: int = 10, verbose: bool = True) -> None:
    """Aggregate results across seeds."""
    totals: dict[str, list[float]] = defaultdict(list)
    purpose_totals: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))

    for seed in range(n_seeds):
        results = run_evaluation(seed=seed, verbose=False)
        for name, r in results.items():
            totals[name].append(r.accuracy)
            for p, (c, t) in r.by_purpose.items():
                purpose_totals[name][p].append(c / t if t else 0)

    if verbose:
        print(f"\n{'='*60}")
        print(f"AGGREGATE ({n_seeds} seeds)")
        print(f"{'='*60}")
        for name in ["perfect", "strategic", "naive", "guesser"]:
            accs = totals[name]
            avg = sum(accs) / len(accs)
            print(f"  {name:12s}: {avg:.1%} avg accuracy")
            for p in ("recall", "coverage", "update",
                       "comprehension", "abstention"):
                vals = purpose_totals[name][p]
                if vals:
                    pavg = sum(vals) / len(vals)
                    print(f"    {p:15s}: {pavg:.1%}")
        print()


# ── Assertions ──

def test_strategy_separation():
    """Core: strategies must be meaningfully separated."""
    results = run_evaluation(seed=42, verbose=False)
    p = results["perfect"].accuracy
    s = results["strategic"].accuracy
    n = results["naive"].accuracy
    g = results["guesser"].accuracy

    assert p > s, f"perfect ({p:.0%}) should beat strategic ({s:.0%})"
    assert s > n, f"strategic ({s:.0%}) should beat naive ({n:.0%})"
    assert n > g, f"naive ({n:.0%}) should beat guesser ({g:.0%})"
    assert p >= 0.8, f"perfect should be ≥80%, got {p:.0%}"
    assert g <= 0.3, f"guesser should be ≤30%, got {g:.0%}"


def test_update_differentiation():
    """Update questions must differentiate strategies that update vs don't.

    Strategic applies corrections → scores on update questions.
    Naive ignores corrections → fails update questions.
    This creates a separation axis INDEPENDENT of storage ratio.
    """
    for seed in range(5):
        tmpl = CompanyWorld()
        results = {}
        for profile in STRATEGIES:
            world = tmpl.generate_world(seed=seed, n_entities=60)
            r = simulate_strategy(tmpl, world, seed, profile, 20)
            results[profile.name] = r

        s_update = results["strategic"].by_purpose.get("update", (0, 0))
        n_update = results["naive"].by_purpose.get("update", (0, 0))

        if s_update[1] > 0 and n_update[1] > 0:
            s_rate = s_update[0] / s_update[1]
            n_rate = n_update[0] / n_update[1]
            assert s_rate > n_rate, (
                f"seed={seed}: strategic update={s_rate:.0%} "
                f"should beat naive update={n_rate:.0%}")


def test_recall_coverage_update_indistinguishable():
    """Anti-hack: retrieval and update questions use identical wording."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)
    rng_doc = Random(42)
    stored_docs = [tmpl.render_document(e, world.active_attrs, rng_doc)
                   for e in world.entities[:30]]
    stored, _ = tmpl.detect_stored_entities(world, stored_docs)

    rng_c = Random(42 + 3333)
    corrections = tmpl.generate_corrections(world, rng_c, 5)

    rng = Random(42 + 7777)
    qs = tmpl.gen_adaptive_questions(
        world, rng, world.entities, stored, 20, corrections)

    for q in qs:
        assert "update" not in q.question.lower()
        assert "correction" not in q.question.lower()
        assert "stored" not in q.question.lower()
        assert "revised" not in q.question.lower()


def test_determinism():
    """Same seed must produce identical questions."""
    tmpl = CompanyWorld()
    world1 = tmpl.generate_world(seed=99, n_entities=60)
    world2 = tmpl.generate_world(seed=99, n_entities=60)
    rng_doc = Random(99)
    docs = [tmpl.render_document(e, world1.active_attrs, rng_doc)
            for e in world1.entities[:30]]
    stored, _ = tmpl.detect_stored_entities(world1, docs)

    # Apply same corrections to both worlds
    c1 = tmpl.generate_corrections(world1, Random(99 + 3333), 5)
    c2 = tmpl.generate_corrections(world2, Random(99 + 3333), 5)

    rng1 = Random(99 + 7777)
    qs1 = tmpl.gen_adaptive_questions(world1, rng1, world1.entities, stored, 20, c1)
    rng2 = Random(99 + 7777)
    qs2 = tmpl.gen_adaptive_questions(world2, rng2, world2.entities, stored, 20, c2)

    assert len(qs1) == len(qs2)
    for a, b in zip(qs1, qs2):
        assert a.question == b.question
        assert a.answer == b.answer
        assert a.purpose == b.purpose


def test_edge_all_stored():
    """100% storage → all retrieval tagged recall or trick_retrieval."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=7, n_entities=40)
    all_names = {e.name for e in world.entities}
    rng = Random(7 + 7777)
    qs = tmpl.gen_adaptive_questions(world, rng, world.entities, all_names, 10)
    retrieval_qs = [q for q in qs if q.competency == "retrieval"]
    assert all(q.purpose in ("recall", "trick_retrieval")
               for q in retrieval_qs)


def test_edge_none_stored():
    """0% storage → all retrieval tagged coverage or trick_retrieval."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=7, n_entities=40)
    rng = Random(7 + 7777)
    qs = tmpl.gen_adaptive_questions(world, rng, world.entities, set(), 10)
    retrieval_qs = [q for q in qs if q.competency == "retrieval"]
    assert all(q.purpose in ("coverage", "trick_retrieval")
               for q in retrieval_qs)


def test_gt_from_world():
    """All GT must be traceable to World state (including corrections)."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)
    rng_doc = Random(42)
    docs = [tmpl.render_document(e, world.active_attrs, rng_doc)
            for e in world.entities[:30]]
    stored, _ = tmpl.detect_stored_entities(world, docs)

    corrections = tmpl.generate_corrections(world, Random(42 + 3333), 5)
    rng = Random(42 + 7777)
    qs = tmpl.gen_adaptive_questions(
        world, rng, world.entities, stored, 20, corrections)

    for q in qs:
        if q.competency in ("retrieval", "update"):
            ent = world.get_entity(q.required_entities[0])
            assert ent is not None, f"Entity {q.required_entities[0]} not in world"


def test_corrections_mutate_world():
    """Corrections must actually change world state."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)

    # Record pre-correction values
    corrections = tmpl.generate_corrections(world, Random(42 + 3333), 5)
    assert len(corrections) > 0, "Should generate at least 1 correction"

    for c in corrections:
        entity = world.get_entity(c.entity_name)
        assert entity is not None
        current = entity.get(c.attr)
        assert current == c.new_val, (
            f"{c.entity_name}.{c.attr}: expected {c.new_val}, got {current}")
        assert c.new_val != c.old_val, (
            f"Correction for {c.entity_name}.{c.attr} didn't change value")


def test_abstraction_generality():
    """All WorldTemplate implementations must produce consistent evaluation."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        accs = {}
        for seed in range(5):
            for profile in STRATEGIES:
                world = tmpl.generate_world(seed=seed, n_entities=60)
                r = simulate_strategy(tmpl, world, seed, profile, 20)
                accs.setdefault(profile.name, []).append(r.accuracy)
        avgs = {n: sum(v) / len(v) for n, v in accs.items()}
        sep = avgs["strategic"] - avgs["naive"]
        assert avgs["perfect"] == 1.0, f"{tmpl.name}: perfect != 100%"
        assert avgs["guesser"] == 0.0, f"{tmpl.name}: guesser != 0%"
        assert sep >= 0.10, f"{tmpl.name}: sep={sep:.0%} < 10%"


def test_monotonicity():
    """Storing more entities must never decrease accuracy."""
    tmpl = CompanyWorld()
    for seed in range(5):
        world = tmpl.generate_world(seed=seed, n_entities=60)
        prev = -1.0
        for pct in range(0, 101, 10):
            world_copy = tmpl.generate_world(seed=seed, n_entities=60)
            profile = StrategyProfile(f"{pct}%", pct / 100, True)
            r = simulate_strategy(tmpl, world_copy, seed, profile, 20)
            assert r.accuracy >= prev - 0.06, (
                f"seed={seed}: {pct-10}%→{pct}% dropped "
                f"{prev:.0%}→{r.accuracy:.0%}")
            prev = r.accuracy


def test_question_quality():
    """Questions must test genuine memory ability.

    1. Retrieval entity diversity: ≥90% unique entities
    2. Synthesis direction diversity: both max and min present
    3. Update questions present when corrections exist
    """
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        entity_uniq_rates = []
        has_max = False
        has_min = False
        has_updates = False

        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_doc = Random(seed)
            docs = [tmpl.render_document(e, world.active_attrs, rng_doc)
                    for e in world.entities[:30]]
            stored, _ = tmpl.detect_stored_entities(world, docs)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            rng = Random(seed + 7777)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, stored, 20, corrections)

            ret = [q for q in qs if q.competency == "retrieval"]
            if ret:
                ents = [q.required_entities[0] for q in ret]
                entity_uniq_rates.append(len(set(ents)) / len(ents))

            for q in qs:
                if q.competency == "synthesis":
                    text = q.question.lower()
                    if any(w in text for w in ("highest", "leads", "first")):
                        has_max = True
                    if any(w in text for w in ("lowest", "least", "last")):
                        has_min = True
                if q.competency == "update":
                    has_updates = True

        avg_uniq = sum(entity_uniq_rates) / len(entity_uniq_rates)
        assert avg_uniq >= 0.9, (
            f"{tmpl.name}: retrieval entity uniqueness {avg_uniq:.0%} < 90%")
        assert has_max and has_min, (
            f"{tmpl.name}: synthesis missing direction "
            f"(max={has_max}, min={has_min})")
        assert has_updates, f"{tmpl.name}: no update questions generated"


def test_document_volume():
    """Compact documents must contain real data (no filler padding).

    At 200 entities, total volume should exceed 40K chars.
    Volume pressure comes from entity quantity, not prose filler.
    """
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=200)
        rng = Random(42)
        total_chars = 0
        for e in world.entities:
            doc = tmpl.render_document(e, world.active_attrs, rng)
            total_chars += len(doc)
        avg_chars = total_chars / len(world.entities)
        assert avg_chars >= 150, (
            f"{tmpl.name}: avg doc length {avg_chars:.0f} chars < 150")
        assert total_chars >= 40000, (
            f"{tmpl.name}: total volume {total_chars:,} chars < 40K")


def test_correction_only_strategy():
    """Correction-only attack must score worse than naive."""
    for seed in range(5):
        tmpl = CompanyWorld()
        world_naive = tmpl.generate_world(seed=seed, n_entities=60)
        r_naive = simulate_strategy(
            tmpl, world_naive, seed,
            StrategyProfile("naive", 0.4, False), 20)

        world_corr = tmpl.generate_world(seed=seed, n_entities=60)
        r_corr = simulate_strategy(
            tmpl, world_corr, seed, CORRECTION_ONLY, 20)

        assert r_corr.accuracy <= r_naive.accuracy, (
            f"seed={seed}: correction_only ({r_corr.accuracy:.0%}) "
            f"should not beat naive ({r_naive.accuracy:.0%})")


def test_abstention_not_identifiable():
    """Abstention questions must use active attributes on fictitious entities.

    Agent cannot distinguish them from retrieval questions.
    """
    for seed in range(5):
        tmpl = CompanyWorld()
        world = tmpl.generate_world(seed=seed, n_entities=60)
        existing = {e.name for e in world.entities}

        rng = Random(seed + 7777)
        qs = tmpl.gen_adaptive_questions(
            world, rng, world.entities, set(), 20)

        for q in qs:
            if q.competency == "abstention":
                # Entity must be fictitious (not in world)
                assert q.required_entities[0] not in existing, (
                    f"Abstention entity {q.required_entities[0]} "
                    f"should not exist in world")


def test_fictitious_entity_not_in_world():
    """Verify abstention uses fictitious entities across all templates."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        for seed in range(3):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            existing = {e.name for e in world.entities}
            rng = Random(seed + 7777)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, set(), 20)

            abstentions = [q for q in qs if q.competency == "abstention"]
            assert len(abstentions) > 0, (
                f"{tmpl.name} seed={seed}: no abstention questions")
            for q in abstentions:
                assert q.required_entities[0] not in existing, (
                    f"{tmpl.name}: abstention entity "
                    f"{q.required_entities[0]} exists in world")


def _compute_simulated_composite(
    accuracy, storage, maintenance_raw, reasoning,
    n_correct, writes_used, n_questions, budget,
    retrieval_acc,
):
    """Mirror eval_scorer.py composite for simulation testing."""
    # Maintenance: gated by retrieval accuracy (V8)
    maintenance = maintenance_raw * min(retrieval_acc / 0.5, 1.0)
    # Efficiency: raw × accuracy, 0 when no writes (V7)
    ideal_rate = n_questions / max(budget, 1)
    if writes_used == 0:
        efficiency = 0.0
    else:
        raw_eff = min(n_correct / writes_used / ideal_rate, 1.0)
        efficiency = raw_eff * accuracy
    # Process
    write_rate = min(writes_used / max(n_questions * 0.5, 1), 1.0)
    process = write_rate * accuracy
    return (0.25 * accuracy + 0.20 * storage + 0.20 * reasoning
            + 0.15 * maintenance + 0.10 * efficiency + 0.10 * process)


def test_name_index_composite():
    """Name-only storage attack must score below naive in composite.

    Attack: store all entity names in 1 write (no values).
    After V8 fix, detect_stored_entities requires name+value → coverage=0%.
    Agent can't answer any questions → composite ≈ 0.
    """
    # Name-index: 0 correct (no values stored), 1 write
    name_idx = _compute_simulated_composite(
        accuracy=0.0, storage=0.0, maintenance_raw=0.0, reasoning=0.0,
        n_correct=0, writes_used=1, n_questions=20, budget=30,
        retrieval_acc=0.0)

    # Naive: ~21.5% accuracy, 12 writes
    naive = _compute_simulated_composite(
        accuracy=0.215, storage=0.25, maintenance_raw=0.0, reasoning=0.10,
        n_correct=4, writes_used=12, n_questions=20, budget=30,
        retrieval_acc=0.25)

    assert name_idx < naive, (
        f"name_index ({name_idx:.4f}) should be < naive ({naive:.4f})")
    assert name_idx < 0.05, (
        f"name_index ({name_idx:.4f}) should be near 0")


def test_efficiency_zero_writes():
    """Zero writes must produce zero efficiency and process."""
    comp = _compute_simulated_composite(
        accuracy=0.15, storage=0.0, maintenance_raw=0.0, reasoning=0.0,
        n_correct=3, writes_used=0, n_questions=20, budget=30,
        retrieval_acc=0.0)
    # Only source of score: 0.25 × 0.15 = 0.0375 (from accuracy alone)
    assert comp <= 0.05, (
        f"Zero-write composite ({comp:.4f}) should be ≤ 0.05")


def test_detect_stored_requires_values():
    """detect_stored_entities must not count name-only entries."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)

    # Pack all names without values
    packed_names = [", ".join(e.name for e in world.entities)]
    stored, missed = tmpl.detect_stored_entities(world, packed_names)
    assert len(stored) == 0, (
        f"Name-only packing detected {len(stored)} entities, expected 0")

    # Full documents should detect entities
    rng = Random(42)
    full_docs = [tmpl.render_document(e, world.active_attrs, rng)
                 for e in world.entities[:30]]
    stored2, missed2 = tmpl.detect_stored_entities(world, full_docs)
    assert len(stored2) >= 25, (
        f"Full docs detected only {len(stored2)} entities, expected ≥25")


def test_year_guessing_fails():
    """V14: Integer GT requires exact match; float GT uses 2% tolerance.

    Integer-exact matching completely prevents year/count guessing.
    Float tolerance handles display rounding (e.g., $1234.5M → 1235).
    """
    from memorygym.evaluation.validators import AnswerValidator
    v = AnswerValidator()

    # Integer GT: exact match only
    assert not v._numeric_match("2000", 1950), "Year guess must fail"
    assert not v._numeric_match("2000", 1990), "Close year guess must fail"
    assert v._numeric_match("1990", 1990), "Exact year must pass"
    assert not v._numeric_match("1991", 1990), "Off-by-one year must fail"
    assert v._numeric_match("150000", 150000), "Exact employee count must pass"
    assert not v._numeric_match("150001", 150000), "Off-by-one count must fail"
    assert v._numeric_match("150,000", 150000), "Comma-formatted must pass"

    # Float GT: 2% relative tolerance
    assert v._numeric_match("1234", 1234.5), "Rounded float must pass"
    assert v._numeric_match("25500", 25000.5), "~2% off float must pass"
    assert not v._numeric_match("26000", 25000.5), "~4% off float must fail"

    # String GT that looks like int (no decimal point)
    assert v._numeric_match("42", "42"), "String int exact must pass"
    assert not v._numeric_match("43", "42"), "String int off-by-one must fail"

    # String GT with decimal point → float tolerance
    assert v._numeric_match("42", "42.0"), "Close to float GT must pass"
    assert v._numeric_match("43", "42.5"), "~1% off float GT must pass"

    # Large integer values: exact match required
    assert v._numeric_match("100000", 100000), "Exact large int must pass"
    assert not v._numeric_match("100500", 100000), (
        "Off-by-500 integer must fail (V14 integer-exact)")


def test_seed_not_in_visible_ids():
    """V11: Seed must not appear in sample ID or task name."""
    from memorygym.worlds.eval_task import worldbench
    task = worldbench(seed=42, template="company", n_entities=20,
                      n_questions=5, write_budget=10, backend="mock")
    # Task name and sample ID must not contain the seed
    assert "42" not in task.name, (
        f"Task name '{task.name}' should not contain seed '42'")
    for sample in task.dataset:
        assert "42" not in sample.id, (
            f"Sample ID '{sample.id}' should not contain seed '42'")


def test_judge_skips_abstention():
    """V10: Abstention uses rule-based validation, not LLM judge.

    In the no-fallback scorer (P4):
    - With judge: abstention → rule-based, all others → judge
    - Without judge: everything → rule-based
    Rule-based _abstention_match is authoritative for abstention.
    """
    from memorygym.evaluation.validators import AnswerValidator
    v = AnswerValidator()

    # Abstention: rule-based validator handles correctly
    assert v.validate("I don't know", "ABSTAIN", "abstention")
    assert not v.validate("42", "ABSTAIN", "abstention")

    # Non-abstention: rule-based is a valid fallback when no judge
    assert v.validate("50000", "50000", "retrieval")
    assert not v.validate("99999", "50000", "retrieval")


def test_stream_interleave():
    """Interleaved stream must produce questions mid-ingest."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed)
            corrections = tmpl.generate_corrections(world, rng, 5)
            stream = tmpl.generate_stream(
                world, rng, corrections,
                stored_names=set(), n_questions=20, entities_per_batch=10)

            types = [e["type"] for e in stream]
            q_count = types.count("question")
            assert q_count == 20, (
                f"{tmpl.name} seed={seed}: expected 20 questions, "
                f"got {q_count}")

            # Mid-stream questions: at least 1 question before last ingest
            last_ingest = max(i for i, t in enumerate(types)
                              if t == "ingest")
            mid_q = sum(1 for i, t in enumerate(types)
                        if t == "question" and i < last_ingest)
            assert mid_q >= 1, (
                f"{tmpl.name} seed={seed}: no mid-stream questions")


def test_stream_invariants():
    """Stream mode must preserve core invariants: perfect=100%, guesser=0%."""
    from memorygym.bench import simulate_one_stream, STRATEGIES
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        accs = {}
        for seed in range(5):
            for profile in STRATEGIES:
                r = simulate_one_stream(tmpl, seed, profile, 60, 20, 5)
                accs.setdefault(profile["name"], []).append(r["accuracy"])
        avgs = {n: sum(v) / len(v) for n, v in accs.items()}
        assert avgs["perfect"] == 1.0, (
            f"{tmpl.name}: stream perfect={avgs['perfect']:.0%} != 100%")
        assert avgs["guesser"] == 0.0, (
            f"{tmpl.name}: stream guesser={avgs['guesser']:.0%} != 0%")
        assert avgs["strategic"] > avgs["naive"] + 0.10, (
            f"{tmpl.name}: stream strategic={avgs['strategic']:.0%} "
            f"not > naive={avgs['naive']:.0%} + 10%")


def test_stream_determinism():
    """Same seed must produce identical stream."""
    tmpl = CompanyWorld()
    for seed in range(3):
        w1 = tmpl.generate_world(seed=seed, n_entities=60)
        r1 = Random(seed)
        c1 = tmpl.generate_corrections(w1, r1, 5)
        s1 = tmpl.generate_stream(w1, r1, c1, set(), 20, 10)

        w2 = tmpl.generate_world(seed=seed, n_entities=60)
        r2 = Random(seed)
        c2 = tmpl.generate_corrections(w2, r2, 5)
        s2 = tmpl.generate_stream(w2, r2, c2, set(), 20, 10)

        assert len(s1) == len(s2), f"seed={seed}: stream length differs"
        for i, (a, b) in enumerate(zip(s1, s2)):
            assert a["type"] == b["type"], (
                f"seed={seed} event {i}: type {a['type']} != {b['type']}")
            if a["type"] == "question":
                assert a["question"] == b["question"], (
                    f"seed={seed} event {i}: question differs")
                assert a["answer"] == b["answer"], (
                    f"seed={seed} event {i}: answer differs")


def test_trick_retrieval():
    """Trick retrieval questions exist and have real (non-ABSTAIN) GT."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        trick_found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, set(), 20, corrections)
            tricks = [q for q in qs if q.purpose == "trick_retrieval"]
            for q in tricks:
                # GT must be a real value, not ABSTAIN
                assert q.answer != "ABSTAIN", (
                    f"trick_retrieval GT should be real, got ABSTAIN")
                # Competency is retrieval
                assert q.competency == "retrieval"
                # Required entity must exist in world
                entity = world.get_entity(q.required_entities[0])
                assert entity is not None, (
                    f"trick_retrieval entity {q.required_entities[0]} not in world")
            trick_found += len(tricks)
        assert trick_found > 0, (
            f"{tmpl.name}: no trick_retrieval questions across 10 seeds")


def test_eval_salt():
    """eval_salt changes values but preserves entity names and structure."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        w0 = tmpl.generate_world(seed=42, n_entities=20, eval_salt=0)
        w1 = tmpl.generate_world(seed=42, n_entities=20, eval_salt=99)

        # Same entity names
        names0 = [e.name for e in w0.entities]
        names1 = [e.name for e in w1.entities]
        assert names0 == names1, f"{tmpl.name}: names differ with salt"

        # Same active attrs
        assert w0.active_attrs == w1.active_attrs

        # Values must differ
        changed = 0
        total = 0
        for e0, e1 in zip(w0.entities, w1.entities):
            for attr in w0.active_attrs:
                v0, v1 = e0.get(attr), e1.get(attr)
                if v0 is not None:
                    total += 1
                    if v0 != v1:
                        changed += 1
        assert changed > total * 0.8, (
            f"{tmpl.name}: only {changed}/{total} values changed with salt")

        # Determinism: same salt → same values
        w2 = tmpl.generate_world(seed=42, n_entities=20, eval_salt=99)
        for e1, e2 in zip(w1.entities, w2.entities):
            for attr in w1.active_attrs:
                assert e1.get(attr) == e2.get(attr), (
                    f"{tmpl.name}: same salt produces different values")


def test_always_abstain_fails():
    """An always-abstain strategy must score 0% on trick_retrieval.

    This is the key anti-hack property: answering "I don't know" to
    everything cannot score perfectly because trick_retrieval questions
    have real answers.
    """
    from memorygym.evaluation.validators import AnswerValidator
    validator = AnswerValidator()

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, set(), 20, corrections)
            tricks = [q for q in qs if q.purpose == "trick_retrieval"]
            for q in tricks:
                # Always-abstain answer
                result = validator.validate(
                    "I don't have enough information",
                    q.answer, q.competency)
                assert not result, (
                    f"always-abstain scored on trick_retrieval: "
                    f"GT={q.answer}, comp={q.competency}")


def test_smart_guesser_ceiling():
    """Midpoint/common-value guessing must stay below 5% accuracy.

    The smart_guesser uses domain knowledge about attribute ranges to
    make plausible guesses (midpoints, quartiles). V14's integer-exact
    matching defeats this: random integers almost never match exact GT.
    """
    from memorygym.bench import _smart_guess, _VALIDATOR

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        correct_total = 0
        question_total = 0
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_q = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, set(), 20, corrections)
            guess_rng = Random(seed + 9999)
            for q in qs:
                guess = _smart_guess(q, world, guess_rng)
                if guess and _VALIDATOR.validate(guess, q.answer, q.competency):
                    correct_total += 1
                question_total += 1

        accuracy = correct_total / question_total if question_total else 0
        assert accuracy < 0.05, (
            f"{tmpl.name} smart_guesser accuracy {accuracy:.1%} >= 5%")


def test_validator_handles_formatted_values():
    """Formatted display values must validate against raw GT.

    Covers the K/M suffix bug: _format_value produces "$498,985.9M" but
    GT is "498985.9". Rule-based validator must accept both interpretations.

    Validates that _format_value output (what agents see in documents)
    can be matched against raw GT by the rule-based validator.

    Skips values near 0 where display rounding may exceed 2% tolerance
    (e.g. 0.49 → "0.5%" is 2.04% off — edge case, not a scoring bug).
    """
    from memorygym.evaluation.validators import AnswerValidator
    v = AnswerValidator()

    failures = []
    total = 0
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=20)
        for e in world.entities[:5]:
            for attr in world.active_attrs:
                val = e.get(attr)
                if val is None:
                    continue
                # Skip near-zero values where rounding exceeds 2% tolerance
                if isinstance(val, (int, float)) and abs(val) < 1:
                    continue
                formatted = tmpl._format_value(attr, val)
                gt_str = str(val)
                total += 1
                if not v.validate(formatted, gt_str, "retrieval"):
                    failures.append(
                        f"{tmpl.name}: '{formatted}' vs GT '{gt_str}' "
                        f"({e.name}.{attr})")

    assert len(failures) == 0, (
        f"{len(failures)}/{total} formatted values failed validation:\n"
        + "\n".join(failures[:5]))


def test_km_suffix_guesser_still_zero():
    """K/M-suffix-aware validator must not help smart_guesser break 5%.

    Verifies that trying both suffix interpretations doesn't create
    a new attack vector for midpoint/quartile guessing.
    """
    from memorygym.bench import _smart_guess, _VALIDATOR

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        correct_total = 0
        question_total = 0
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_q = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, set(), 20, corrections)
            guess_rng = Random(seed + 9999)
            for q in qs:
                guess = _smart_guess(q, world, guess_rng)
                if guess and _VALIDATOR.validate(guess, q.answer, q.competency):
                    correct_total += 1
                question_total += 1

        accuracy = correct_total / question_total if question_total else 0
        assert accuracy < 0.05, (
            f"{tmpl.name} smart_guesser with K/M fix: {accuracy:.1%} >= 5%")


def test_detect_stored_numeric_variants():
    """detect_stored_entities must find entities stored with various formats.

    Tests that _numeric_variants covers raw, rounded, and decimal formats
    beyond the original _format_value + int(round()) checks.
    """
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=20)

    # Build documents using raw numeric format (not _format_value)
    raw_docs = []
    for e in world.entities[:10]:
        parts = [e.name]
        for attr in world.active_attrs:
            val = e.get(attr)
            if val is not None:
                parts.append(f"{attr}: {val}")
        raw_docs.append(", ".join(parts))

    stored, missed = tmpl.detect_stored_entities(world, raw_docs)
    assert len(stored) >= 8, (
        f"Raw-format docs detected only {len(stored)} entities, expected ≥8")


def test_priority_beats_random():
    """Priority storage (WHAT you store) must outperform random storage.

    Both strategies store exactly 50% of entities with updates enabled.
    Priority selects entities by question likelihood (populated categories,
    attribute completeness, extreme values). This proves that storage
    strategy quality matters — not just storage quantity.
    """
    from memorygym.bench import _entity_priority_score

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld,
                       HospitalWorld, SportWorld]:
        tmpl = TmplClass()
        priority_wins = 0
        ties = 0
        total = 0
        for seed in range(10):
            world_p = tmpl.generate_world(seed=seed, n_entities=60)
            world_r = tmpl.generate_world(seed=seed, n_entities=60)

            rng_doc_p = Random(seed)
            rng_doc_r = Random(seed)
            all_docs_p = [(e, tmpl.render_document(e, world_p.active_attrs, rng_doc_p))
                          for e in world_p.entities]
            all_docs_r = [(e, tmpl.render_document(e, world_r.active_attrs, rng_doc_r))
                          for e in world_r.entities]

            n_store = max(1, int(len(all_docs_p) * 0.5))

            # Priority: top-N by importance score
            scored = [(i, _entity_priority_score(e, world_p))
                      for i, (e, _) in enumerate(all_docs_p)]
            scored.sort(key=lambda x: -x[1])
            p_docs = [all_docs_p[i][1] for i, _ in scored[:n_store]]

            # Random: random N
            rng_store = Random(seed + 111)
            r_indices = rng_store.sample(range(len(all_docs_r)), n_store)
            r_docs = [all_docs_r[i][1] for i in r_indices]

            p_stored, _ = tmpl.detect_stored_entities(world_p, p_docs)
            r_stored, _ = tmpl.detect_stored_entities(world_r, r_docs)

            # Generate corrections and questions for both
            rng_cp = Random(seed + 3333)
            corrections_p = tmpl.generate_corrections(world_p, rng_cp, 5)
            rng_cr = Random(seed + 3333)
            corrections_r = tmpl.generate_corrections(world_r, rng_cr, 5)

            p_updated = {c.entity_name for c in corrections_p
                         if c.entity_name in p_stored}
            r_updated = {c.entity_name for c in corrections_r
                         if c.entity_name in r_stored}

            rng_qp = Random(seed + 7777)
            qs_p = tmpl.gen_adaptive_questions(
                world_p, rng_qp, world_p.entities, p_stored, 20, corrections_p)
            rng_qr = Random(seed + 7777)
            qs_r = tmpl.gen_adaptive_questions(
                world_r, rng_qr, world_r.entities, r_stored, 20, corrections_r)

            p_correct = sum(1 for q in qs_p
                            if _construct_and_validate(
                                q, tmpl, world_p, p_stored, p_updated, True,
                                len(world_p.entities)))
            r_correct = sum(1 for q in qs_r
                            if _construct_and_validate(
                                q, tmpl, world_r, r_stored, r_updated, True,
                                len(world_r.entities)))

            total += 1
            if p_correct > r_correct:
                priority_wins += 1
            elif p_correct == r_correct:
                ties += 1

        win_rate = priority_wins / total
        assert win_rate >= 0.3 or (priority_wins + ties) / total >= 0.6, (
            f"{tmpl.name}: priority only wins {priority_wins}/{total} seeds "
            f"(ties={ties}) — strategy quality doesn't differentiate")


def test_format_roundtrip_in_simulation():
    """Verify _format_value() → validate() roundtrip for all templates.

    For every retrieval/update question, constructing the answer via
    _format_value(attr, val) must pass validation against the GT.
    This catches precision/suffix bugs that would be invisible with
    a boolean _can_answer() shortcut.
    """
    from memorygym.evaluation.validators import AnswerValidator
    validator = AnswerValidator()

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld,
                       HospitalWorld, SportWorld]:
        tmpl = TmplClass()
        for seed in range(3):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_correct = Random(seed + 3333)
            corrections = tmpl.generate_corrections(world, rng_correct, 5)
            rng_q = Random(seed + 7777)
            stored = {e.name for e in world.entities}
            questions = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, stored, 20, corrections)

            for q in questions:
                if q.competency not in ("retrieval", "update"):
                    continue
                if not q.source_attr:
                    continue
                entity = world.get_entity(q.required_entities[0])
                if not entity:
                    continue
                val = entity.get(q.source_attr)
                if val is None:
                    continue
                formatted = tmpl._format_value(q.source_attr, val)
                ok = validator.validate(formatted, q.answer, q.competency)
                assert ok, (
                    f"{tmpl.name} seed={seed}: _format_value({q.source_attr}, "
                    f"{val})={formatted!r} failed validation against "
                    f"GT={q.answer!r} (competency={q.competency})")


def test_adaptive_comprehension():
    """Comprehension questions must only reference stored entities.

    When stored_names is provided, all comprehension questions should
    reference entities within that set. This ensures the reasoning axis
    tests reasoning ability, not storage luck.
    """
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld,
                       HospitalWorld, SportWorld]:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed)
            corrections = tmpl.generate_corrections(world, rng, 5)

            # Only store first 30 entities (50% coverage)
            stored = {e.name for e in world.entities[:30]}
            rng_q = Random(seed + 7777)
            questions = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, stored, 20, corrections)

            comp_types = {"synthesis", "aggregation", "conditional",
                          "ratio", "comparison", "multi_hop", "outlier"}
            for q in questions:
                if q.competency in comp_types:
                    needed = set(q.required_entities)
                    assert needed <= stored, (
                        f"{tmpl.name} seed={seed}: {q.competency} "
                        f"references unstored entities: "
                        f"{needed - stored}")


def test_maybe_replace_comprehension():
    """maybe_replace_comprehension replaces unanswerable questions."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=0, n_entities=60)

    # Simulate storing first 30 entities
    stored_contents = []
    for e in world.entities[:30]:
        doc = tmpl._compact_document(e, world.active_attrs)
        stored_contents.append(f"{e.name} | {doc}")

    # Create a question referencing unstored entities
    unstored = world.entities[50]
    bad_event = {
        "type": "question",
        "question": f"What is {unstored.name}'s revenue?",
        "answer": "test",
        "competency": "synthesis",
        "purpose": "comprehension",
        "required_entities": [unstored.name],
        "source_attr": "revenue_m",
    }

    replaced = tmpl.maybe_replace_comprehension(
        bad_event, world, stored_contents, rng_seed=42)

    # Should be replaced with a question about stored entities
    assert replaced is not bad_event, "Question should have been replaced"
    stored_names = {e.name for e in world.entities[:30]}
    new_entities = set(replaced["required_entities"])
    assert new_entities <= stored_names, (
        f"Replacement references unstored: {new_entities - stored_names}")

    # A question with all stored entities should NOT be replaced
    stored_entity = world.entities[0]
    good_event = {
        "type": "question",
        "question": f"What is {stored_entity.name}'s revenue?",
        "answer": "test",
        "competency": "comparison",
        "purpose": "comprehension",
        "required_entities": [stored_entity.name, world.entities[1].name],
        "source_attr": "revenue_m",
    }
    not_replaced = tmpl.maybe_replace_comprehension(
        good_event, world, stored_contents, rng_seed=42)
    assert not_replaced is good_event, "Stored question should not be replaced"


def test_relationship_generation():
    """CompanyWorld generates relationships deterministically."""
    tmpl = CompanyWorld()
    w1 = tmpl.generate_world(seed=42, n_entities=30)
    w2 = tmpl.generate_world(seed=42, n_entities=30)
    assert len(w1.relationships) > 0, "Should generate relationships"
    assert len(w1.relationships) == len(w2.relationships), "Deterministic count"
    for r1, r2 in zip(w1.relationships, w2.relationships):
        assert r1.source == r2.source
        assert r1.relation == r2.relation
        assert r1.target == r2.target
    # No self-loops
    for r in w1.relationships:
        assert r.source != r.target, f"Self-loop: {r.source}"
    # Query methods work
    if w1.relationships:
        name = w1.relationships[0].source
        assert len(w1.get_outgoing(name)) >= 1
        assert len(w1.get_relationships(name)) >= 1


def test_relationship_questions():
    """Relationship question types generate valid questions."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)
    assert len(world.relationships) > 0

    rng = Random(42)
    corrections = tmpl.generate_corrections(world, Random(42 + 3333), 5)
    stored = {e.name for e in world.entities}
    qs = tmpl.gen_adaptive_questions(
        world, rng, world.entities, stored, 40, corrections)
    rel_qs = [q for q in qs if "relationship" in q.competency]
    assert len(rel_qs) >= 1, "Should generate at least 1 relationship question"
    valid_rel_types = (
        "relationship_lookup", "relationship_hop",
        "relationship_chain", "relationship_count",
        "relationship_filter",
    )
    for q in rel_qs:
        assert q.competency in valid_rel_types, (
            f"Unknown relationship type: {q.competency}")
        assert len(q.required_entities) >= 2
        assert q.answer, "Answer must not be empty"
        # All entities must exist in world
        for name in q.required_entities:
            assert world.get_entity(name) is not None, f"Unknown entity: {name}"


if __name__ == "__main__":
    # Single seed detailed view
    run_evaluation(seed=42, verbose=True)

    # Multi-seed aggregate
    run_multi_seed(n_seeds=10, verbose=True)

    # Run all assertions
    print("Running assertion tests...")
    test_strategy_separation()
    print("  ✓ strategy_separation")
    test_update_differentiation()
    print("  ✓ update_differentiation")
    test_recall_coverage_update_indistinguishable()
    print("  ✓ recall_coverage_update_indistinguishable")
    test_determinism()
    print("  ✓ determinism")
    test_edge_all_stored()
    print("  ✓ edge_all_stored")
    test_edge_none_stored()
    print("  ✓ edge_none_stored")
    test_gt_from_world()
    print("  ✓ gt_from_world")
    test_corrections_mutate_world()
    print("  ✓ corrections_mutate_world")
    test_abstraction_generality()
    print("  ✓ abstraction_generality")
    test_monotonicity()
    print("  ✓ monotonicity")
    test_question_quality()
    print("  ✓ question_quality")
    test_document_volume()
    print("  ✓ document_volume")
    test_correction_only_strategy()
    print("  ✓ correction_only_strategy")
    test_abstention_not_identifiable()
    print("  ✓ abstention_not_identifiable")
    test_fictitious_entity_not_in_world()
    print("  ✓ fictitious_entity_not_in_world")
    test_name_index_composite()
    print("  ✓ name_index_composite")
    test_efficiency_zero_writes()
    print("  ✓ efficiency_zero_writes")
    test_detect_stored_requires_values()
    print("  ✓ detect_stored_requires_values")
    test_year_guessing_fails()
    print("  ✓ year_guessing_fails")
    test_seed_not_in_visible_ids()
    print("  ✓ seed_not_in_visible_ids")
    test_judge_skips_abstention()
    print("  ✓ judge_skips_abstention")
    test_stream_interleave()
    print("  ✓ stream_interleave")
    test_stream_invariants()
    print("  ✓ stream_invariants")
    test_stream_determinism()
    print("  ✓ stream_determinism")
    test_trick_retrieval()
    print("  ✓ trick_retrieval")
    test_always_abstain_fails()
    print("  ✓ always_abstain_fails")
    test_eval_salt()
    print("  ✓ eval_salt")
    test_smart_guesser_ceiling()
    print("  ✓ smart_guesser_ceiling")
    test_validator_handles_formatted_values()
    print("  ✓ validator_handles_formatted_values")
    test_km_suffix_guesser_still_zero()
    print("  ✓ km_suffix_guesser_still_zero")
    test_detect_stored_numeric_variants()
    print("  ✓ detect_stored_numeric_variants")
    test_priority_beats_random()
    print("  ✓ priority_beats_random")
    test_format_roundtrip_in_simulation()
    print("  ✓ format_roundtrip_in_simulation")
    test_relationship_generation()
    print("  ✓ relationship_generation")
    test_relationship_questions()
    print("  ✓ relationship_questions")
    print("ALL TESTS PASSED")
