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
    Contradiction, Correction, GeneratedQA, World, WorldTemplate,
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
            assert r.accuracy >= prev - 0.12, (
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

        for seed in range(20):
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
        assert avg_chars >= 120, (
            f"{tmpl.name}: avg doc length {avg_chars:.0f} chars < 120")
        assert total_chars >= 30000, (
            f"{tmpl.name}: total volume {total_chars:,} chars < 30K")


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
    print("ALL TESTS PASSED")
