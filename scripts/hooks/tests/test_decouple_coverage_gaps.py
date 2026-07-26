#!/usr/bin/env python3
"""
Coverage-gap tests for the decoupled component-graph transform (ADR-036, `graphing/decouple.py`).

An adversarial coverage review (independent of the Phase 1 RED-suite authors) audited
`test_decouple_transform.py` and `test_decouple_guards.py` against ADR-036 and found
gaps in what those suites exercise -- distinct from whether the existing tests are
individually correct. This module closes the high-severity gaps (H1-H3) and
medium-severity gaps (M1-M6) the review identified.

Unlike the original Phase 1 RED suites, `decouple.py` already existed when this module
was written (82/82 of the existing tests passed against it). Some tests below were
GREEN against the implementation at that time (the coverage gap was closed with no
code change needed); others were RED, specifying new required behavior or documenting
a genuine bug in the implementation at that time. All gaps have since been closed and
every test in this module now passes; each test class's docstring states its original
GREEN/RED status and, where applicable, the fix that made it GREEN.

Two results are flagged prominently below:
  - H2 (arm-label / port-id collision across broadcasts) was RED against the
    implementation this suite was originally written against: the "bare label unless
    the arm is its root's only arm for that concern" rule scoped "for that concern"
    per-channel (i.e., per (src_root, tgt_root, concern)), not per (tgt_root, concern)
    across all channels landing in that root. Two single-arm channels from different
    src_roots landing in the same tgt_root under the same concern label produced an
    identical port id and an identical arm label -- confirmed via `verify_plan()`,
    which raised `S7 violated: port id collision(s)` against this fixture. This has
    since been fixed (the multi-arm decision is now scoped to (tgt_root, concern)
    across every channel landing there, not to one channel's own edges), and this
    class's tests are now GREEN regression coverage rather than RED bug documentation.
  - M6 (slug collision between distinct concern labels) reproduces the same underlying
    port-id-collision defect from a different angle (two distinct labels slugging
    identically) but is written as a GREEN documentation test per the coverage review's
    own instruction: full collision detection is deferred to Phase 2's S7 self-check, so
    this test's job is only to prove the collision is representable and pin what happens
    today, not to demand a fix in Phase 1.
"""

import random
import sys
from pathlib import Path

# Add scripts/hooks directory to path (matches test_base_graph.py / test_decouple_transform.py
# convention). Must run before the riskmap_validator imports below.
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing.decouple import (  # noqa: E402
    AspectDecl,
    ConcernDecl,
    EmissionConfig,
    build_decoupled_plan,
    check_emission_drift,
    slug,
    verify_plan,
)
from riskmap_validator.models import ComponentNode  # noqa: E402
from riskmap_validator.utils import parse_components_yaml  # noqa: E402

# ============================================================================
# Shared helpers (duplicated from test_decouple_transform.py / test_decouple_guards.py
# rather than imported, so this file has no load-bearing dependency on those modules'
# internals and can be reviewed/moved independently).
# ============================================================================


def _node(category: str, to_edges: list[str] | None = None, subcategory: str | None = None) -> ComponentNode:
    """Build a minimal ComponentNode. The transform classifies purely off `forward_map` +
    `category`/`subcategory`, so `from_edges` is always empty here."""
    return ComponentNode(
        title="Test Node",
        category=category,
        to_edges=to_edges or [],
        from_edges=[],
        subcategory=subcategory,
    )


def _forward_map(components: dict[str, ComponentNode]) -> dict[str, list[str]]:
    """Derive forward_map the same way validator.build_edge_maps does (copy of to_edges)."""
    return {cid: node.to_edges[:] for cid, node in components.items()}


INFRA = "componentsInfrastructure"
MODEL = "componentsModel"
APP = "componentsApplication"
TOOLS = "componentsTools"


# ============================================================================
# H1: refused-lift cascade with zero `concerns` coverage on the aspect's in-edges
# ============================================================================


class TestH1RefusedLiftCascadeWithNoConcernsCoverage:
    """
    GREEN against the current implementation.

    Every refusal test in test_decouple_transform.py / test_decouple_guards.py
    pre-covers the aspect's in-edges with a `concerns` entry before the lift is refused.
    This fixture triggers G-O1 (block-orphan) with ZERO concerns coverage on the
    aspect's three in-edges, proving the reclassify-to-channel path also runs the G-C3
    fallback-label synthesis correctly (not a special "refused with no label" state).
    """

    def _fixture(self):
        components = {
            "componentModelSource0": _node(MODEL, to_edges=["componentAspectSink"]),
            "componentModelSource1": _node(MODEL, to_edges=["componentAspectSink"]),
            "componentModelSource2": _node(MODEL, to_edges=["componentAspectSink"]),
            "componentAspectSink": _node(INFRA, subcategory="componentsIsolatedBlock"),
            "componentBlockSibling": _node(
                INFRA, to_edges=["componentModelElsewhere"], subcategory="componentsIsolatedBlock"
            ),
            "componentModelElsewhere": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentAspectSink", min_cross_in_degree=3),),
            concerns=(
                # Only the sibling edge is covered -- the aspect's 3 in-edges have NO
                # concerns entry at all, unlike every existing refusal fixture.
                ConcernDecl(label="sibling flow", edges=(("componentBlockSibling", "componentModelElsewhere"),)),
            ),
        )
        return components, cfg

    def test_lift_is_refused_by_block_orphan_guard(self):
        """
        Given: fixture (c)-shaped corpus but with zero concerns coverage on the
        aspect's in-edges
        When: build_decoupled_plan runs
        Then: G-O1 fires and the lift is refused, same as the covered case
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.lifted_aspects == []

    def test_refused_edges_are_reclassified_as_a_channel_not_dropped(self):
        """
        Given: the same fixture
        When: build_decoupled_plan runs
        Then: the 3 refused edges land in a broadcast carrying the G-C3 synthesized
        fallback label '<srcRoot>→<tgtRoot> flow' -- they are never silently dropped
        just because no concerns entry names them
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        fallback_label = f"{MODEL}→{INFRA} flow"
        matching = [b for b in plan.broadcasts if b.label == fallback_label]
        assert matching, f"expected a broadcast labelled {fallback_label!r}, got: {plan.broadcasts}"
        broadcast = matching[0]
        # All 3 edges share the same (single) target, so they collapse into one arm.
        assert broadcast.arm_count == 1
        assert broadcast.channels[0].arms[0].edges == (
            ("componentModelSource0", "componentAspectSink"),
            ("componentModelSource1", "componentAspectSink"),
            ("componentModelSource2", "componentAspectSink"),
        )

    def test_conservation_counters_balance(self):
        """intra_drawn(0) + 2*collapsed(0) + channelled(4) + lifted(0) == total_edges(4)."""
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.intra_drawn_count == 0
        assert plan.collapsed_pair_count == 0
        assert plan.channelled_count == 4  # 3 aspect in-edges + 1 sibling edge
        assert plan.lifted_count == 0
        assert plan.total_edges == 4

    def test_check_emission_drift_returns_both_the_guard_and_the_fallback_warning_in_one_call(self):
        """
        Given: the same fixture
        When: check_emission_drift is called ONCE
        Then: both the G-O1 block-orphan warning AND the G-C3 fallback-label warnings
        (one per refused edge) are present in the single returned list -- and that list
        is identical to plan.warnings (single source of truth, D2's shared _classify pass)
        """
        components, cfg = self._fixture()
        forward_map = _forward_map(components)
        plan = build_decoupled_plan(forward_map, components, cfg)
        drift = check_emission_drift(forward_map, components, cfg)

        assert drift == plan.warnings
        has_orphan_guard = any(
            "componentAspectSink" in w and "componentsIsolatedBlock" in w and "zero drawn intra edges" in w
            for w in drift
        )
        has_fallback = any(
            "componentModelSource0" in w and "synthesizing fallback label" in w and f"{MODEL}→{INFRA} flow" in w
            for w in drift
        )
        assert has_orphan_guard, f"expected a G-O1 block-orphan warning in: {drift}"
        assert has_fallback, f"expected a G-C3 fallback-label warning in: {drift}"


# ============================================================================
# H2: arm-label / port-id collision across broadcasts (was RED -- documented a real
# bug; now GREEN regression coverage for the fix)
# ============================================================================


class TestH2ArmLabelPortIdCollisionAcrossBroadcasts:
    """
    GREEN against the current implementation -- this class now provides regression
    coverage for a genuine port-id/label collision bug that has since been fixed.

    `_build_arms()` used to compute `multi_arm = len(targets_sorted) > 1` PER CHANNEL,
    where a Channel is keyed by `(src_root, tgt_root, concern)` (see `_group_channels`).
    So "the arm is its root's only arm for that concern" (plan §B step 5 / ADR D6) was
    scoped per (src_root, tgt_root, concern) -- NOT per (tgt_root, concern) across every
    channel landing in that root. Two channels with the SAME (tgt_root, concern) but
    DIFFERENT src_root each independently saw themselves as single-arm and each
    constructed the bare port id `p_in_{tgt_root_abbrev}_{concern_slug}` with the bare
    label -- identical strings, landing at two genuinely different target nodes.

    Confirmed at the time against `decouple.py`:
        broadcast(src_root=Infra) -> channel(Infra, Tools, "shared concern") -> arm
            target=componentToolsM1, port_id='p_in_tools_shared_concern', label='shared concern'
        broadcast(src_root=Model) -> channel(Model, Tools, "shared concern") -> arm
            target=componentToolsM2, port_id='p_in_tools_shared_concern', label='shared concern'
    `verify_plan()` raised `S7 violated: port id collision(s): ['p_in_tools_shared_concern']`
    against this exact fixture at the time -- so the D7 self-check already flagged this
    as wrong; the transform itself just didn't prevent or disambiguate it before
    returning the plan.

    `_group_channels` now computes the distinct-target union per (tgt_root, concern)
    across ALL channels before any channel's arms are built, so `multi_arm` is correctly
    scoped and this exact fixture no longer collides. These tests assert CORRECTNESS
    (port-id and per-band label uniqueness) and now pass; they are kept as permanent
    regression coverage for the fix.
    """

    def _fixture(self):
        components = {
            "componentInfraSrc": _node(INFRA, to_edges=["componentToolsM1"]),
            "componentModelSrc": _node(MODEL, to_edges=["componentToolsM2"]),
            "componentToolsM1": _node(TOOLS),
            "componentToolsM2": _node(TOOLS),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="shared concern", edges=(("componentInfraSrc", "componentToolsM1"),)),
                ConcernDecl(label="shared concern", edges=(("componentModelSrc", "componentToolsM2"),)),
            ),
        )
        return components, cfg

    def test_two_single_arm_channels_from_different_src_roots_still_land_at_distinct_targets(self):
        """
        Given: two single-arm channels, different src_root (Infra, Model), same
        tgt_root (Tools) and same concern label, each landing at a DIFFERENT target
        When: build_decoupled_plan runs
        Then (sanity, expected to already hold): each channel still reports its own
        correct landing target -- the bug is in the ids/labels assigned to those arms,
        not in which node they land at
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        targets = {arm.target for b in plan.broadcasts for c in b.channels for arm in c.arms}
        assert targets == {"componentToolsM1", "componentToolsM2"}

    def test_arm_port_ids_are_unique_across_the_whole_plan(self):
        """
        Given: the same fixture
        When: build_decoupled_plan runs
        Then: every arm port id in the plan is distinct (D7 S7) -- two arms landing at
        two different nodes must never share a port id, since a Mermaid port id is a
        node identity
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        port_ids = [arm.port_id for b in plan.broadcasts for c in b.channels for arm in c.arms]
        assert len(port_ids) == len(set(port_ids)), f"duplicate arm port id(s) in: {port_ids}"

    def test_arm_labels_are_unique_within_the_shared_target_root_band(self):
        """
        Given: the same fixture
        When: build_decoupled_plan runs
        Then: per-band ingress-label uniqueness holds (D7 S4) -- a reader looking at
        the Tools band must be able to tell the two arms apart by label
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        tools_labels = [
            arm.label for b in plan.broadcasts for c in b.channels if c.tgt_root == TOOLS for arm in c.arms
        ]
        assert len(tools_labels) == len(set(tools_labels)), f"duplicate ingress label(s) in: {tools_labels}"

    def test_verify_plan_does_not_raise_on_this_exact_fixture(self):
        """
        Given: the same fixture -- the exact two-single-arm-channels-converging-on-one-
        (tgt_root, concern) shape that used to trigger the H2 port-id collision
        When: verify_plan() (the D7 IR-level self-check) runs over the built plan
        Then: it does not raise -- regression coverage for the H2 fix. This is an
        end-to-end check across the full D7 rubric (S1/S4/S5/S7 all in one call) and
        complements the two narrower unit-level assertions above, which each pin one
        invariant (port-id uniqueness, label uniqueness) directly; this one confirms
        the whole self-check passes cleanly on the fixture that used to fail it.
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        verify_plan(plan, components)  # should not raise


# ============================================================================
# H3: aspect with mixed intra + cross in-edges
# ============================================================================


class TestH3AspectWithMixedIntraAndCrossInEdges:
    """GREEN against the current implementation."""

    def _fixture(self):
        """
        A candidate aspect with 3 cross in-edges (from Model, satisfying the threshold)
        AND one intra in-edge (from a same-block Infra sibling). Plan §B step 2: "intra
        in-edges (none today) would stay drawn." This is the corpus-independent test of
        that clause.
        """
        components = {
            "componentModelSource0": _node(MODEL, to_edges=["componentAspectSink"]),
            "componentModelSource1": _node(MODEL, to_edges=["componentAspectSink"]),
            "componentModelSource2": _node(MODEL, to_edges=["componentAspectSink"]),
            "componentAspectSink": _node(INFRA, subcategory="componentsBlockX"),
            "componentIntraFeeder": _node(INFRA, to_edges=["componentAspectSink"], subcategory="componentsBlockX"),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentAspectSink", min_cross_in_degree=3),),
            concerns=(
                ConcernDecl(
                    label="sink flow",
                    edges=tuple((f"componentModelSource{i}", "componentAspectSink") for i in range(3)),
                ),
            ),
        )
        return components, cfg

    def test_only_cross_in_edges_are_lifted(self):
        """
        Given: the mixed-in-edges fixture
        When: build_decoupled_plan runs
        Then: the lift succeeds (candidacy passes: sink, cross in-degree 3 >= 3, block
        not orphaned -- the intra feeder edge itself keeps the block non-orphaned) and
        ONLY the 3 cross in-edges appear in the lifted-aspect header inventory
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.lifted_aspects) == 1
        lifted = plan.lifted_aspects[0]
        assert lifted.aspect_id == "componentAspectSink"
        assert set(lifted.edges) == {
            ("componentModelSource0", "componentAspectSink"),
            ("componentModelSource1", "componentAspectSink"),
            ("componentModelSource2", "componentAspectSink"),
        }
        assert ("componentIntraFeeder", "componentAspectSink") not in lifted.edges

    def test_the_intra_in_edge_remains_in_the_drawn_intra_edge_set(self):
        """The intra in-edge is never lifted -- it stays a normal drawn intra edge."""
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert ("componentIntraFeeder", "componentAspectSink") in plan.drawn_intra_edges

    def test_conservation_counters_balance_including_the_intra_survivor(self):
        """intra_drawn(1) + 2*collapsed(0) + channelled(0) + lifted(3) == total_edges(4)."""
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.intra_drawn_count == 1
        assert plan.collapsed_pair_count == 0
        assert plan.channelled_count == 0
        assert plan.lifted_count == 3
        assert plan.total_edges == 4
        assert plan.warnings == []

    def test_zero_cross_in_edges_variant_fails_candidacy_without_reaching_block_orphan_check(self):
        """
        Given: the SAME aspect, but with zero cross in-edges (only the intra in-edge)
        When: build_decoupled_plan runs
        Then: candidacy fails on the cross-in-degree threshold (G-A3) before the G-O1
        block-orphan check is ever evaluated -- no G-O1 message appears, only G-A3.
        The intra edge alone is enough to keep the block non-orphaned (it is drawn),
        which is exactly why G-O1 would not have fired even if reached; the point of
        this test is the short-circuit itself, since G-A3 refusal happens strictly
        before the G-O1 check runs in `_evaluate_aspects`.
        """
        components = {
            "componentAspectSink": _node(INFRA, subcategory="componentsBlockX"),
            "componentIntraFeeder": _node(INFRA, to_edges=["componentAspectSink"], subcategory="componentsBlockX"),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentAspectSink", min_cross_in_degree=1),),
            concerns=(),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert plan.lifted_aspects == []
        assert ("componentIntraFeeder", "componentAspectSink") in plan.drawn_intra_edges
        assert any("cross in-degree 0" in w for w in plan.warnings)
        assert not any("would leave its block" in w for w in plan.warnings)


# ============================================================================
# M1: G-A1/G-C1/G-C2 degradation at the transform level (not just the guard-message level)
# ============================================================================


class TestM1GuardDegradationAtTheTransformLevel:
    """GREEN against the current implementation -- all four sub-cases below."""

    def test_g_a1_dead_aspect_id_is_ignored_and_the_plan_is_otherwise_correctly_built(self):
        """
        (a) G-A1: a configured aspect id absent from the corpus.

        Given: emission.aspects names a component id that does not exist
        When: build_decoupled_plan runs
        Then: the dead entry is ignored (no lift, no crash) and the rest of the plan --
        the one real cross edge -- is built exactly as if the dead entry were absent
        """
        components = {
            "componentRealSink": _node(INFRA),
            "componentModelSource": _node(MODEL, to_edges=["componentRealSink"]),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentGhost", min_cross_in_degree=1),),
            concerns=(ConcernDecl(label="flow", edges=(("componentModelSource", "componentRealSink"),)),),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert plan.lifted_aspects == []
        assert len(plan.broadcasts) == 1
        assert plan.broadcasts[0].label == "flow"
        assert plan.broadcasts[0].arm_count == 1
        assert plan.channelled_count == 1
        assert plan.lifted_count == 0
        assert plan.total_edges == 1
        assert any("componentGhost" in w for w in plan.warnings)

    def test_g_c1_dead_edge_reference_does_not_suppress_its_sibling_live_edge(self):
        """
        (b) G-C1: a concerns entry naming one live edge and one dead (nonexistent) edge.

        Given: one concerns entry listing two (src, tgt) tuples, one real and one
        naming an edge that does not exist in the corpus
        When: build_decoupled_plan runs
        Then: the live sibling edge in the SAME entry is still correctly channelled
        under that entry's label -- a bad tuple in the list must not drop its siblings
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA", "componentModelB"]),
            "componentModelA": _node(MODEL),
            "componentModelB": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="mixed flow",
                    edges=(
                        ("componentInfraA", "componentModelA"),
                        ("componentInfraA", "componentModelZZZ"),  # dead: no such edge
                    ),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert any("componentModelZZZ" in w for w in plan.warnings)
        mixed_flow = next(b for b in plan.broadcasts if b.label == "mixed flow")
        landed_targets = {arm.target for c in mixed_flow.channels for arm in c.arms}
        assert landed_targets == {"componentModelA"}
        assert plan.channelled_count == 2  # componentModelA (named) + componentModelB (fallback)
        assert plan.total_edges == 2

    def test_g_c2_recategorized_edge_lands_in_drawn_intra_edges_not_channelled(self):
        """
        (c1) G-C2, non-mirrored: a concerns entry names an edge whose endpoints now
        share a category.

        Given: a concerns entry naming (A, B), where a corpus edit has since put both
        A and B in the same category
        When: build_decoupled_plan runs
        Then: the edge appears in drawn_intra_edges (not channelled, not lost) and no
        broadcast is produced for it
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentInfraB"]),
            "componentInfraB": _node(INFRA),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(ConcernDecl(label="formerly cross", edges=(("componentInfraA", "componentInfraB"),)),),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert ("componentInfraA", "componentInfraB") in plan.drawn_intra_edges
        assert plan.broadcasts == ()
        assert plan.collapsed_pairs == []
        assert plan.intra_drawn_count == 1
        assert plan.total_edges == 1
        assert any("componentInfraB" in w and INFRA in w for w in plan.warnings)

    def test_g_c2_recategorized_edge_participates_correctly_in_mirror_pair_collapse(self):
        """
        (c2) G-C2, mirrored: same recategorization, but the corpus also has the reverse
        edge, forming a same-category mirror pair.

        Given: a concerns entry naming (A, B) as cross (now stale), and the corpus also
        has the reverse edge (B, A) -- both endpoints share a category and neither is a
        PEP
        When: build_decoupled_plan runs
        Then: the pair collapses to a single collapsed_pairs entry, exactly like any
        other PEP-free intra mirror pair -- the G-C2 recategorization does not exempt
        it from the normal collapse-eligibility rule
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentInfraB"]),
            "componentInfraB": _node(INFRA, to_edges=["componentInfraA"]),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(ConcernDecl(label="formerly cross", edges=(("componentInfraA", "componentInfraB"),)),),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        collapsed = {frozenset(p) for p in plan.collapsed_pairs}
        assert frozenset({"componentInfraA", "componentInfraB"}) in collapsed
        assert plan.drawn_intra_edges == []
        assert plan.collapsed_pair_count == 1
        assert plan.total_edges == 2


# ============================================================================
# M2: shuffled-input determinism at the transform level (IR structure, not Mermaid text)
# ============================================================================


class TestM2ShuffledInputDeterminismAtTheTransformLevel:
    """GREEN against the current implementation."""

    def test_shuffled_dict_insertion_order_produces_an_identical_plan_on_the_live_corpus(self, repo_root: Path):
        """
        Given: the live corpus, built into two `components`/`forward_map` dict pairs
        with independently shuffled key insertion order
        When: build_decoupled_plan runs on each
        Then: the resulting DecoupledPlan instances are equal in every field --
        broadcast order, arm order within a channel, drawn-intra-edge order, collapsed
        pairs, band links, lifted aspects, clusters, and pep wrappers -- not just the
        eventual Mermaid text (that equivalence is Phase 2's job; this pins the IR
        itself, which is sorted-iteration-driven per D7 regardless of input dict order)
        """
        components_live = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml")
        forward_map_live = _forward_map(components_live)
        cfg = EmissionConfig(
            mode="decoupled", aspects=(AspectDecl(id="componentSecureLogging", min_cross_in_degree=10),)
        )

        rng = random.Random(20260723)
        shuffled_component_items = list(components_live.items())
        rng.shuffle(shuffled_component_items)
        components_shuffled = dict(shuffled_component_items)

        shuffled_forward_items = list(forward_map_live.items())
        rng.shuffle(shuffled_forward_items)
        forward_map_shuffled = dict(shuffled_forward_items)

        plan_a = build_decoupled_plan(forward_map_live, components_live, cfg)
        plan_b = build_decoupled_plan(forward_map_shuffled, components_shuffled, cfg)

        # Whole-dataclass equality first (broadest check: every field, in order).
        assert plan_a == plan_b
        # Then a few explicit field checks, named per the gap description, so a future
        # regression that breaks dataclass __eq__ (e.g. a field becoming a set) still
        # gets a legible per-field failure message.
        assert plan_a.broadcasts == plan_b.broadcasts
        assert plan_a.drawn_intra_edges == plan_b.drawn_intra_edges
        assert plan_a.collapsed_pairs == plan_b.collapsed_pairs
        assert plan_a.lifted_aspects == plan_b.lifted_aspects
        assert plan_a.band_links == plan_b.band_links


# ============================================================================
# M3: reachability diagnostic needs a pinned IR home (was RED -- specified new
# behavior; now GREEN, the field has since been added)
# ============================================================================


class TestM3ReachabilityDiagnosticNeedsAPinnedIrHome:
    """
    GREEN against the current implementation -- `_reachability_diagnostic()` (step 8)
    used to only call `logging.getLogger(__name__).info(...)` and touch no
    `DecoupledPlan` field, so nothing in the IR could hold its findings and Phase 2 had
    nowhere to consume them. `DecoupledPlan.diagnostics: list[str]` has since been added,
    populated with advisory findings ONLY (never touching `warnings`, never altering
    `arms`/`channels`/output).

    These tests pin the field's permanent contract: populated with a legible finding
    when a multi-arm channel's targets are mutually intra-reachable, left as an empty
    list when no finding applies, and never touching `warnings` or the drawn output.
    """

    def _fixture(self):
        """
        A 2-arm channel whose two targets are mutually intra-reachable: componentAppA
        and componentAppB have a same-cluster mirror pair between them (so each is
        reachable from the other via intra_edges), while both are also independently
        cross-channel targets from an Infra hub under one concern.
        """
        components = {
            "componentInfraHub": _node(INFRA, to_edges=["componentAppA", "componentAppB"]),
            "componentAppA": _node(APP, to_edges=["componentAppB"]),
            "componentAppB": _node(APP, to_edges=["componentAppA"]),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="hub flow",
                    edges=(
                        ("componentInfraHub", "componentAppA"),
                        ("componentInfraHub", "componentAppB"),
                    ),
                ),
            ),
        )
        return components, cfg

    def test_diagnostics_field_is_populated_for_mutually_reachable_arm_targets(self):
        """
        Given: the same fixture
        When: build_decoupled_plan runs
        Then: `plan.diagnostics` is non-empty and describes the reachable-arms
        situation (mentions both target ids), `plan.warnings` is unaffected (still
        empty -- this is advisory only, never a drift warning), and the drawn
        output/arm structure is completely unchanged by the diagnostic's presence
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert plan.diagnostics
        assert any("componentAppA" in d and "componentAppB" in d for d in plan.diagnostics)
        assert plan.warnings == []
        # Arm/channel structure must be untouched by the diagnostic's presence.
        channel = plan.broadcasts[0].channels[0]
        assert {arm.target for arm in channel.arms} == {"componentAppA", "componentAppB"}

    def test_diagnostics_defaults_to_empty_list_when_no_reachability_finding_applies(self):
        """
        Given: a multi-arm channel (same hub, same concern, two Application targets)
        whose targets are NOT mutually intra-reachable -- no intra edge exists between
        componentAppA and componentAppB at all
        When: build_decoupled_plan runs
        Then: `plan.diagnostics` is the empty list -- the field is present on every
        plan (not conditionally attached only when a finding exists) and defaults to
        empty when the reachability diagnostic has nothing to report
        """
        components = {
            "componentInfraHub": _node(INFRA, to_edges=["componentAppA", "componentAppB"]),
            "componentAppA": _node(APP),
            "componentAppB": _node(APP),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="hub flow",
                    edges=(
                        ("componentInfraHub", "componentAppA"),
                        ("componentInfraHub", "componentAppB"),
                    ),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.diagnostics == []


# ============================================================================
# M4: both-endpoints-PEP-wrapped mirror pair
# ============================================================================


class TestM4BothEndpointsPepWrappedMirrorPair:
    """GREEN against the current implementation."""

    def _fixture(self):
        components = {
            "componentAPolicyEnforcementPoint": _node(APP, to_edges=["componentBPolicyEnforcementPoint"]),
            "componentBPolicyEnforcementPoint": _node(APP, to_edges=["componentAPolicyEnforcementPoint"]),
        }
        cfg = EmissionConfig(mode="decoupled")
        return components, cfg

    def test_both_endpoints_get_wrappers(self):
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert "componentAPolicyEnforcementPoint" in plan.pep_wrappers
        assert "componentBPolicyEnforcementPoint" in plan.pep_wrappers

    def test_the_pair_never_collapses(self):
        """Per D1: neither endpoint qualifies for collapse when either is wrapped --
        a fortiori when BOTH are wrapped."""
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.collapsed_pairs == []

    def test_both_directions_retarget_through_the_others_wrap_ports(self):
        """
        Given: the both-wrapped mirror pair
        When: build_decoupled_plan runs
        Then: `pepA_out -> pepB_in` and `pepB_out -> pepA_in` are both drawn (the
        implementation's actual retarget grammar: each side's outgoing direction uses
        its own `out_id`, landing on the partner's `in_id`)
        """
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        wrapper_a = plan.pep_wrappers["componentAPolicyEnforcementPoint"]
        wrapper_b = plan.pep_wrappers["componentBPolicyEnforcementPoint"]
        assert (wrapper_a.out_id, wrapper_b.in_id) in plan.drawn_intra_edges
        assert (wrapper_b.out_id, wrapper_a.in_id) in plan.drawn_intra_edges
        assert plan.intra_drawn_count == 2
        assert plan.collapsed_pair_count == 0
        assert plan.total_edges == 2


# ============================================================================
# M5: two aspects lifting simultaneously
# ============================================================================


class TestM5TwoAspectsLiftingSimultaneously:
    """GREEN against the current implementation."""

    def _fixture(self):
        components = {}
        for i in range(5):
            components[f"componentModelSourceA{i}"] = _node(MODEL, to_edges=["componentAspectSinkA"])
        for i in range(5):
            components[f"componentAppSourceB{i}"] = _node(APP, to_edges=["componentAspectSinkB"])
        components["componentAspectSinkA"] = _node(INFRA, subcategory="componentsBlockX")
        components["componentAspectSinkB"] = _node(TOOLS, subcategory="componentsBlockY")
        # Each sink's block gets its own independent intra feeder so neither lift risks
        # G-O1 -- this fixture isolates "two independent lifts both succeed" from any
        # block-orphan interaction.
        components["componentInfraFeeder"] = _node(
            INFRA, to_edges=["componentAspectSinkA"], subcategory="componentsBlockX"
        )
        components["componentToolsFeeder"] = _node(
            TOOLS, to_edges=["componentAspectSinkB"], subcategory="componentsBlockY"
        )
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(
                AspectDecl(id="componentAspectSinkA", min_cross_in_degree=5),
                AspectDecl(id="componentAspectSinkB", min_cross_in_degree=5),
            ),
        )
        return components, cfg

    def test_both_aspects_appear_as_separate_lifted_aspect_entries(self):
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.lifted_aspects) == 2
        lifted_by_id = {la.aspect_id: la for la in plan.lifted_aspects}
        assert set(lifted_by_id) == {"componentAspectSinkA", "componentAspectSinkB"}
        assert len(lifted_by_id["componentAspectSinkA"].edges) == 5
        assert len(lifted_by_id["componentAspectSinkB"].edges) == 5

    def test_combined_conservation_counters_are_correct(self):
        """intra_drawn(2) + 2*collapsed(0) + channelled(0) + lifted(10) == total_edges(12)."""
        components, cfg = self._fixture()
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.intra_drawn_count == 2
        assert plan.collapsed_pair_count == 0
        assert plan.channelled_count == 0
        assert plan.lifted_count == 10
        assert plan.total_edges == 12
        assert plan.warnings == []


# ============================================================================
# M6: slug collision between distinct concern labels (GREEN documentation test)
# ============================================================================


class TestM6SlugCollisionBetweenDistinctConcernLabels:
    """
    GREEN against the current implementation -- deliberately a documentation test, per
    the coverage review's own framing: full collision detection/prevention at
    registration time is out of scope for Phase 1 (it is S7's job in Phase 2's
    self-check, already exercised indirectly by `verify_plan()` -- see H2). This test's
    job is only to prove the collision is representable in `slug()` and pin what the
    transform does with it today.

    This reproduces the SAME underlying defect as H2 (port-id collision) from a
    different trigger -- two distinct, non-colliding
    concern LABELS that happen to slug identically, rather than one label used from two
    src_roots. `check_emission_drift`/`build_decoupled_plan` currently have no
    registration-time slug-collision guard at all (no G-* entry covers it), so this is
    silent today unless a caller separately runs `verify_plan()`. Whether to fix this
    now (Phase 1) or defer to Phase 2's S7 self-check is a call for the
    code-reviewer/orchestrator; this test does not take a position on that, it just
    pins current behavior so the decision is made with full information.
    """

    def test_the_collision_pair_is_representable_in_slug(self):
        """slug() collapses '/' and ' ' identically, so "tool/hosting" and "tool hosting"
        produce the same slug -- the exact pair named in the task description."""
        assert slug("tool/hosting") == slug("tool hosting") == "tool_hosting"

    def test_two_distinct_labels_stay_distinct_broadcasts_but_collide_on_port_id_today(self):
        """
        Given: two concerns entries with distinct labels that slug identically, each
        covering a different edge from a different Infra source to a different Tools
        target
        When: build_decoupled_plan runs
        Then: the two broadcasts are NOT silently merged (labels remain distinct
        strings, so the semantic distinction the contributor intended is preserved at
        the label level) -- but their egress port ids, and their single arms' port
        ids, ARE identical today. This is the known, documented gap: nothing currently
        detects or disambiguates a slug collision between distinct labels.
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentToolsA"]),
            "componentInfraB": _node(INFRA, to_edges=["componentToolsB"]),
            "componentToolsA": _node(TOOLS),
            "componentToolsB": _node(TOOLS),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="tool/hosting", edges=(("componentInfraA", "componentToolsA"),)),
                ConcernDecl(label="tool hosting", edges=(("componentInfraB", "componentToolsB"),)),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert len(plan.broadcasts) == 2
        labels = {b.label for b in plan.broadcasts}
        assert labels == {"tool/hosting", "tool hosting"}

        broadcast_by_label = {b.label: b for b in plan.broadcasts}
        broadcast_slash = broadcast_by_label["tool/hosting"]
        broadcast_space = broadcast_by_label["tool hosting"]

        # KNOWN GAP (documented, not fixed in Phase 1): egress port ids collide despite
        # the labels being distinct.
        assert broadcast_slash.egress_port_id == broadcast_space.egress_port_id == "p_out_infra_tool_hosting"

        arm_slash = broadcast_slash.channels[0].arms[0]
        arm_space = broadcast_space.channels[0].arms[0]
        # KNOWN GAP (documented, not fixed in Phase 1): ingress arm port ids also
        # collide, despite landing at two different target nodes.
        assert arm_slash.port_id == arm_space.port_id == "p_in_tools_tool_hosting"
        assert arm_slash.target != arm_space.target

        # verify_plan() already flags this today via the S7 uniqueness check -- callers
        # who run it get a loud failure; the transform itself does not prevent it.
        try:
            verify_plan(plan, components)
        except AssertionError as exc:
            assert "S7" in str(exc)
        else:
            raise AssertionError(
                "expected verify_plan() to raise on this slug collision; if this no "
                "longer raises, the collision has been fixed and this test needs updating"
            )


"""
Test Summary
============
Total test functions: 26 across 9 test classes.

Coverage areas (adversarial coverage-review gaps H1-H3, M1-M6):
- H1 (refused-lift cascade, zero concerns coverage): 4 tests. GREEN.
- H2 (arm-label/port-id collision across broadcasts): 4 tests. GREEN -- was RED,
  documenting a real bug in `_build_arms`'s per-channel (not per-(tgt_root, concern))
  multi-arm scoping; `_group_channels` has since been fixed to scope the decision
  across all channels sharing (tgt_root, concern), and these tests are now permanent
  regression coverage for that fix (including a direct `verify_plan()` no-raise check).
- H3 (aspect with mixed intra + cross in-edges): 4 tests. GREEN, including the
  zero-cross-in-edges/G-A3-short-circuits-before-G-O1 variant.
- M1 (G-A1/G-C1/G-C2 degradation at the transform level): 4 tests. GREEN.
- M2 (shuffled-input determinism, IR-level): 1 test (live corpus). GREEN.
- M3 (reachability diagnostic IR home): 2 tests. GREEN -- was RED, since `DecoupledPlan`
  had no `diagnostics` field; the field now exists and is exercised for both the
  populated case (mutually-reachable arm targets) and the empty-list default case.
- M4 (both-endpoints-PEP-wrapped mirror pair): 3 tests. GREEN.
- M5 (two aspects lifting simultaneously): 2 tests. GREEN.
- M6 (slug collision between distinct concern labels): 2 tests. GREEN by design --
  documents the current (colliding) behavior rather than demanding a fix, per the
  coverage review's own framing that full collision handling is Phase 2's S7 job.

Notes for the code-reviewer:
- H2 and M6 surface the SAME underlying class of defect (arm/broadcast port-id
  construction needs a global uniqueness guarantee) from two different angles: H2 via
  one label reused across src_roots landing in one tgt_root (now fixed at the
  transform level), M6 via two distinct labels that slug identically (still open,
  deliberately deferred to Phase 2's S7 self-check per the coverage review's framing).
  M6's gap is unaffected by the H2 fix -- distinct concern labels are never merged by
  `_group_channels`'s (tgt_root, concern) grouping, so two channels with different
  labels that happen to slug identically still each see themselves as single-arm and
  still collide on port id. Whether to also close M6 now or leave it for Phase 2's S7
  self-check is a call for the code-reviewer/orchestrator; this suite does not take a
  position on that.
"""
