#!/usr/bin/env python3
"""
Tests for the decoupled component-graph transform (ADR-036, `graphing/decouple.py`).

`graphing/decouple.py` implements this contract against ADR-036 D1-D7. This suite pins
that implementation as a regression guard.

Contract under test (as fixed by this test suite; the implementation was derived
from it):

    AspectDecl(id, min_cross_in_degree)
    ConcernDecl(label, edges: tuple[tuple[str, str], ...])
    EmissionConfig(mode, aspects=(), concerns=(), port_styles=None)
    PepWrapper(pep_id, in_id, out_id, wrap_id)
    Arm(target, landing_id, port_id, label, edges)
    Channel(src_root, tgt_root, concern, edges, arms)
    Broadcast(egress_port_id, src_root, label, channels, arm_count)
    LiftedAspect(aspect_id, edges)
    Block(id, members, entry_id, exit_id, pure_feeders, exit_skips)
    Cluster(id, members, blocks)
    DecoupledPlan(clusters, pep_wrappers, broadcasts, lifted_aspects,
                  drawn_intra_edges, collapsed_pairs, band_links, warnings,
                  intra_drawn_count, collapsed_pair_count, channelled_count,
                  lifted_count, total_edges)

    slug(text) -> str
    root_slug(category_id) -> str
    target_short_name(component_id) -> str
    pep_wrap_base(component_id) -> str
    build_decoupled_plan(forward_map, components, emission_cfg) -> DecoupledPlan
    check_emission_drift(forward_map, components, emission_cfg) -> list[str]

`root_slug`/`Channel.src_root`/`Channel.tgt_root` distinction: `root(n) = components[n].category`
(D2) is the FULL category id (e.g. "componentsInfrastructure") and is what `Channel.src_root`/
`tgt_root` store; `root_slug()` is the separate, ID-grammar-only abbreviation (D6: "infra",
"model", "app", "tools") used solely to build port ids. Tests below exercise both and never
conflate them.

Test Coverage
=============
1. Grammar primitives: slug(), root_slug(), target_short_name(), pep_wrap_base() —
   exact literal assertions, including the two ADR-quoted slug() edge cases.
2. Port-id / arm-label grammar reproduced from the ADR D6 runtime-hosting worked example
   (literal ids quoted directly from docs/adr/036-decoupled-component-graph-emission.md).
3. Partition (D2): intra vs cross classification by root(n), via the minimal 2-cluster
   single-broadcast fixture (fixture a).
4. Aspect candidacy (D4): sink test, cross-in-degree threshold boundary, per-entry
   threshold, source-exclusion.
5. Concern resolution: covered, uncovered (fallback + warning), double-covered
   (lexicographic resolution + warning).
6. Channel + broadcast keying (D2, D5): grouping by (srcRoot, tgtRoot, concern) and
   broadcast merge by (srcRoot, concern, label); anti-fusion (distinct concerns over the
   same cluster pair never merge).
7. D6 arm splitting: single-target, multi-target (no landing selection, no frequency
   bias), mirrored cross-cluster pair (four ports, no collapse).
8. PEP wrap -> retarget -> collapse ordering (fixture b): a PEP-involved intra mirror pair
   never collapses and its landing retargets through the wrapper's `_in` port; a
   PEP-free intra mirror pair collapses to a single drawn pair.
9. Aspect + block-orphan guard interaction (fixture c): the lift is refused and edges
   are reclassified as a channel instead of silently lifting.
10. Bands / blocks: entry/exit id detection by the `.*(Input|Output)Handling$` regex
    (moderate depth — this is shared "recipe mechanics", not corpus-specific judgment,
    so exhaustive coverage is not required here).
11. Live-corpus inventory: `build_decoupled_plan()` against the real
    `risk-map/yaml/components.yaml`, asserting registry numbers this suite's author
    independently re-derived from the corpus.
12. ADR-036 D8 (display-layer acronym substitution, arm-label site): the real
    "identity & authz" broadcast's 4 PEP-landing arm labels substitute to "PEP",
    each keeping its own distinguishing prefix; the port ids computed from those
    same targets stay byte-identical (the D8 hard invariant); a synthetic PDP+PEP
    mixed channel proves the closed set doesn't generalize to PDP.
13. ADR-036 D9 (consult-class channel landing): a consult-class arm lands on its
    target's component id even when the target is PEP-wrapped, while a data-class
    arm to the same wrapped target keeps its `_in` landing; port ids and labels are
    unchanged by the classification. Covered synthetically (one target, two
    concerns, side by side, plus near-miss labels pinning exact-match) and against
    the live corpus's four wrapped `identity & authz` targets.
"""

import sys
from pathlib import Path

import pytest
import yaml

# Add scripts/hooks directory to path (matches test_base_graph.py convention).
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing.decouple import (  # noqa: E402
    AspectDecl,
    ConcernDecl,
    EmissionConfig,
    build_decoupled_plan,
    pep_wrap_base,
    root_slug,
    slug,
    target_short_name,
)
from riskmap_validator.graphing.graph_utils import _parse_emission_config  # noqa: E402
from riskmap_validator.models import ComponentNode  # noqa: E402
from riskmap_validator.utils import parse_components_yaml  # noqa: E402

# ============================================================================
# Shared helpers
# ============================================================================


def _node(category: str, to_edges: list[str] | None = None, subcategory: str | None = None) -> ComponentNode:
    """Build a minimal ComponentNode. `from_edges` is irrelevant to the transform
    (it classifies purely off `forward_map` + `category`), so it is always empty here."""
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
TOOLS = "componentsExternalTools"


# ============================================================================
# 1. Grammar primitives
# ============================================================================


class TestSlugGrammar:
    """
    slug(): lowercase, '&' dropped (not underscored), non-alphanumeric runs -> single
    '_', trimmed. Both literal examples are quoted directly from slug()'s own docstring.
    """

    def test_slug_drops_ampersand_identity_authz(self):
        """
        Given: the exact example "identity & authz" from slug()'s docstring
        When: slug() is called
        Then: '&' is dropped entirely (not replaced with '_'), yielding "identity_authz"
        """
        assert slug("identity & authz") == "identity_authz"

    def test_slug_collapses_slash_run_inference_serving(self):
        """
        Given: the exact example "inference / serving" from slug()'s docstring
        When: slug() is called
        Then: the "/ " run of non-alphanumeric chars collapses to a single '_'
        """
        assert slug("inference / serving") == "inference_serving"

    def test_slug_lowercases(self):
        """
        Given: a mixed-case label
        When: slug() is called
        Then: output is fully lowercase
        """
        assert slug("Model Artifacts") == "model_artifacts"

    def test_slug_collapses_multiple_non_alnum_chars_to_one_underscore(self):
        """
        Given: a label with a multi-character non-alphanumeric run
        When: slug() is called
        Then: the whole run becomes exactly one underscore, not one per character
        """
        assert slug("tool//discovery") == "tool_discovery"

    def test_slug_trims_leading_and_trailing_non_alnum(self):
        """
        Given: a label with leading/trailing whitespace
        When: slug() is called
        Then: no leading or trailing underscore survives
        """
        assert slug("  hosting  ") == "hosting"

    def test_slug_plus_sign_becomes_underscore_run(self):
        """
        Given: the "app + agent egress" concern label (emission.concerns entry #10)
        When: slug() is called
        Then: '+' is not dropped (only '&' is dropped, per slug()'s definition) — it is swept into the
        surrounding non-alnum run and collapsed to a single '_', same as any other
        non-alphanumeric separator.
        """
        assert slug("app + agent egress") == "app_agent_egress"


class TestRootSlugGrammar:
    """root_slug(): the D6-normative abbreviations, plus the documented fallback rule."""

    @pytest.mark.parametrize(
        "category_id,expected",
        [
            (INFRA, "infra"),
            (MODEL, "model"),
            (APP, "app"),
            (TOOLS, "tools"),
        ],
    )
    def test_root_slug_normative_abbreviations(self, category_id, expected):
        """
        Given: each of the four current top-level category ids
        When: root_slug() is called
        Then: the exact D6-normative abbreviation is returned
        """
        assert root_slug(category_id) == expected

    def test_root_slug_fallback_for_unknown_category(self):
        """
        Given: a category id with no declared abbreviation (a hypothetical future category)
        When: root_slug() is called
        Then: falls back to lowercase of the id minus the 'components' prefix (root_slug()'s fallback rule)
        """
        assert root_slug("componentsGovernance") == "governance"


class TestTargetShortNameGrammar:
    """
    target_short_name(): component id minus 'component' prefix, camel-split, lowercased,
    space-joined — id-derived, not title-derived. This is the FULL uncompressed name
    (e.g. "authorization policy enforcement point"), not the informal ADR-prose
    abbreviations like "AuthzPEP" — those are shorthand in prose only, and the
    verbosity is an accepted, known cost of deriving the name from the id.
    """

    def test_target_short_name_reasoning_core(self):
        """
        Given: the exact ADR D6 example component id
        When: target_short_name() is called
        Then: returns the exact quoted short name "reasoning core"
        """
        assert target_short_name("componentReasoningCore") == "reasoning core"

    def test_target_short_name_single_word(self):
        """
        Given: a component id with a single camel word after the prefix
        When: target_short_name() is called
        Then: returns that one word, lowercased
        """
        assert target_short_name("componentApplication") == "application"

    def test_target_short_name_long_pep_id_is_not_abbreviated(self):
        """
        Given: a long PEP component id
        When: target_short_name() is called
        Then: returns the full camel-split name, not the "AuthzPEP"-style prose shorthand
        (verbosity is an accepted cost, not a rule this function works around)
        """
        assert (
            target_short_name("componentAuthorizationPolicyEnforcementPoint")
            == "authorization policy enforcement point"
        )

    def test_target_short_name_the_model(self):
        """
        Given: a component id where the camel-split includes a stopword-like segment
        When: target_short_name() is called
        Then: still splits and lowercases every camel segment ("The", "Model")
        """
        assert target_short_name("componentTheModel") == "the model"


class TestPepWrapBaseGrammar:
    """
    pep_wrap_base(): the abbreviated base used to build a PEP wrapper's in/out/wrap ids.
    The literal example in pep_wrap_base()'s own docstring ("agentNetworkPep") fixes the
    "PolicyEnforcementPoint" -> "Pep" abbreviation; in_id/out_id/wrap_id are then
    `<base>_in` / `<base>_out` / `<base>_wrap`.
    """

    def test_pep_wrap_base_matches_the_quoted_plan_example(self):
        """
        Given: the exact component id used in pep_wrap_base()'s own docstring example
        When: pep_wrap_base() is called
        Then: returns "agentNetworkPep" (so wrap_id becomes "agentNetworkPep_wrap",
        the literal string quoted in that docstring)
        """
        assert pep_wrap_base("componentAgentNetworkPolicyEnforcementPoint") == "agentNetworkPep"

    def test_pep_wrap_base_applies_consistently_to_other_pep_ids(self):
        """
        Given: a different PEP id, same "PolicyEnforcementPoint" suffix
        When: pep_wrap_base() is called
        Then: the same abbreviation rule applies (not a one-off hardcoded string)

        This is a derived case, not a literal ADR quote — it exists to prove the rule
        generalizes rather than being special-cased for the one quoted example.
        """
        assert pep_wrap_base("componentApplicationNetworkPolicyEnforcementPoint") == "applicationNetworkPep"


# ============================================================================
# 2. Port-id / arm-label grammar — reproduced verbatim from ADR D6
# ============================================================================


class TestPortIdAndArmLabelGrammarFromAdrExample:
    """
    Reproduces the ADR-036 D6 "runtime hosting" worked example exactly (component ids,
    concern label, and the four port ids/labels are all quoted directly from the ADR's
    Mermaid code block) to pin the port-id and arm-label grammar with literal assertions.
    """

    @pytest.fixture
    def runtime_hosting_plan(self):
        components = {
            "componentRuntimeHosting": _node(
                INFRA,
                to_edges=["componentModelServing", "componentApplication", "componentReasoningCore"],
            ),
            "componentModelServing": _node(MODEL),
            "componentApplication": _node(APP),
            "componentReasoningCore": _node(APP),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="runtime hosting",
                    edges=(
                        ("componentRuntimeHosting", "componentModelServing"),
                        ("componentRuntimeHosting", "componentApplication"),
                        ("componentRuntimeHosting", "componentReasoningCore"),
                    ),
                ),
            ),
        )
        return build_decoupled_plan(_forward_map(components), components, cfg)

    def test_egress_port_id_matches_adr_literal(self, runtime_hosting_plan):
        """Egress port id must be exactly `p_out_infra_runtime_hosting`, per the ADR block."""
        broadcasts = runtime_hosting_plan.broadcasts
        assert len(broadcasts) == 1
        assert broadcasts[0].egress_port_id == "p_out_infra_runtime_hosting"

    def test_broadcast_arm_count_is_three(self, runtime_hosting_plan):
        """The `⇢ 3` in the ADR header comment — three distinct targets, three arms total."""
        assert runtime_hosting_plan.broadcasts[0].arm_count == 3

    def test_single_arm_channel_port_id_has_no_suffix(self, runtime_hosting_plan):
        """Model channel has only one arm (componentModelServing) -> bare port id, no target suffix."""
        broadcast = runtime_hosting_plan.broadcasts[0]
        model_channel = next(c for c in broadcast.channels if c.tgt_root == MODEL)
        assert len(model_channel.arms) == 1
        assert model_channel.arms[0].port_id == "p_in_model_runtime_hosting"

    def test_single_arm_channel_label_is_bare_concern_label(self, runtime_hosting_plan):
        """Model arm's label is the bare concern label (its root's only arm for this concern)."""
        broadcast = runtime_hosting_plan.broadcasts[0]
        model_channel = next(c for c in broadcast.channels if c.tgt_root == MODEL)
        assert model_channel.arms[0].label == "runtime hosting"

    def test_multi_arm_channel_port_ids_have_target_suffix(self, runtime_hosting_plan):
        """App channel has two arms -> both port ids carry the slugged target short-name suffix."""
        broadcast = runtime_hosting_plan.broadcasts[0]
        app_channel = next(c for c in broadcast.channels if c.tgt_root == APP)
        port_ids = {arm.port_id for arm in app_channel.arms}
        assert port_ids == {
            "p_in_app_runtime_hosting_application",
            "p_in_app_runtime_hosting_reasoning_core",
        }

    def test_multi_arm_channel_labels_use_arrow_and_target_short_name(self, runtime_hosting_plan):
        """App arm labels are "<concern> → <target-short-name>", per D6's per-band uniqueness rule."""
        broadcast = runtime_hosting_plan.broadcasts[0]
        app_channel = next(c for c in broadcast.channels if c.tgt_root == APP)
        labels = {arm.label for arm in app_channel.arms}
        assert labels == {
            "runtime hosting → application",
            "runtime hosting → reasoning core",
        }


# ============================================================================
# 3. Partition (D2) + basic pipeline correctness — fixture (a)
# ============================================================================


@pytest.fixture
def two_cluster_single_broadcast_fixture():
    """
    Fixture (a): minimal 2-cluster corpus with exactly one broadcast.

    componentInfraSource has one intra edge (-> componentInfraHelper) and one cross
    edge (-> componentModelTarget). This isolates partition + single-channel/broadcast
    construction from every other pipeline concern (no aspects, no PEPs, no multi-arm).
    """
    components = {
        "componentInfraSource": _node(INFRA, to_edges=["componentInfraHelper", "componentModelTarget"]),
        "componentInfraHelper": _node(INFRA),
        "componentModelTarget": _node(MODEL),
    }
    cfg = EmissionConfig(
        mode="decoupled",
        concerns=(ConcernDecl(label="widget flow", edges=(("componentInfraSource", "componentModelTarget"),)),),
    )
    return components, cfg


class TestPartitionAndBasicPipeline:
    def test_intra_edge_is_drawn_not_channelled(self, two_cluster_single_broadcast_fixture):
        """
        Given: fixture (a)
        When: build_decoupled_plan runs
        Then: the intra edge (same root(n) on both ends) is in drawn_intra_edges
        """
        components, cfg = two_cluster_single_broadcast_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert ("componentInfraSource", "componentInfraHelper") in plan.drawn_intra_edges

    def test_cross_edge_is_not_drawn_intra(self, two_cluster_single_broadcast_fixture):
        """The cross edge must never appear in drawn_intra_edges (D1: zero drawn cross edges)."""
        components, cfg = two_cluster_single_broadcast_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert ("componentInfraSource", "componentModelTarget") not in plan.drawn_intra_edges

    def test_exactly_one_broadcast_is_produced(self, two_cluster_single_broadcast_fixture):
        """Given: fixture (a). Then: exactly one broadcast, one channel, one arm."""
        components, cfg = two_cluster_single_broadcast_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.broadcasts) == 1
        assert len(plan.broadcasts[0].channels) == 1
        assert len(plan.broadcasts[0].channels[0].arms) == 1
        assert plan.broadcasts[0].channels[0].arms[0].target == "componentModelTarget"

    def test_conservation_counters_are_consistent(self, two_cluster_single_broadcast_fixture):
        """intra_drawn(1) + 2*collapsed(0) + channelled(1) + lifted(0) == total_edges(2)."""
        components, cfg = two_cluster_single_broadcast_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.intra_drawn_count == 1
        assert plan.collapsed_pair_count == 0
        assert plan.channelled_count == 1
        assert plan.lifted_count == 0
        assert plan.total_edges == 2
        assert (
            plan.intra_drawn_count + 2 * plan.collapsed_pair_count + plan.channelled_count + plan.lifted_count
            == plan.total_edges
        )

    def test_no_warnings_for_well_formed_config(self, two_cluster_single_broadcast_fixture):
        """A fully-covered, drift-free config produces zero warnings."""
        components, cfg = two_cluster_single_broadcast_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.warnings == []


# ============================================================================
# 4. Aspect candidacy (D4)
# ============================================================================


class TestAspectCandidacy:
    def _sink_fixture(self, n_cross_in: int, extra_out_edge: bool = False):
        """Build a sink candidate with exactly n_cross_in cross in-edges from distinct
        Model-cluster sources, optionally giving the sink an outgoing edge (sink violation)."""
        components = {}
        for i in range(n_cross_in):
            src = f"componentModelSource{i}"
            components[src] = _node(MODEL, to_edges=["componentAspectSink"])
        sink_out_edges = ["componentInfraOther"] if extra_out_edge else []
        components["componentAspectSink"] = _node(INFRA, to_edges=sink_out_edges, subcategory="componentsBlockX")
        components["componentInfraOther"] = _node(INFRA, subcategory="componentsBlockX")
        # give the block another intra edge unrelated to the sink so G-O1 (block-orphan)
        # never fires in these tests -- this test class isolates D4 candidacy only.
        components["componentInfraFeeder"] = _node(
            INFRA, to_edges=["componentInfraOther"], subcategory="componentsBlockX"
        )
        return components

    def test_out_degree_zero_is_required_for_candidacy(self):
        """
        Given: a configured aspect with 12 cross in-edges but ALSO an outgoing edge
        When: build_decoupled_plan runs
        Then: the sink test fails (out-degree != 0); the lift is refused, edges become
        a channel instead, and a warning is recorded (G-A2, message contract tested
        separately in test_decouple_guards.py)
        """
        components = self._sink_fixture(n_cross_in=12, extra_out_edge=True)
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentAspectSink", min_cross_in_degree=10),),
            concerns=(
                ConcernDecl(
                    label="sink flow",
                    edges=tuple((f"componentModelSource{i}", "componentAspectSink") for i in range(12)),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.lifted_aspects == []
        assert plan.warnings != []
        # The 12 edges must still be drawn somewhere -- as a channel, not silently dropped.
        assert any(b.label == "sink flow" for b in plan.broadcasts)

    @pytest.mark.parametrize(
        "cross_in_degree,expect_lift",
        [
            (9, False),  # one below threshold
            (10, True),  # exactly at threshold
            (11, True),  # one above threshold
        ],
    )
    def test_cross_in_degree_threshold_boundary(self, cross_in_degree, expect_lift):
        """
        Given: a pure sink with cross in-degree at/around the configured threshold (10)
        When: build_decoupled_plan runs
        Then: the lift occurs iff cross in-degree >= min_cross_in_degree (D4: "meets")
        """
        components = self._sink_fixture(n_cross_in=cross_in_degree)
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentAspectSink", min_cross_in_degree=10),),
            concerns=(
                ConcernDecl(
                    label="sink flow",
                    edges=tuple(
                        (f"componentModelSource{i}", "componentAspectSink") for i in range(cross_in_degree)
                    ),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        if expect_lift:
            assert len(plan.lifted_aspects) == 1
            assert plan.lifted_aspects[0].aspect_id == "componentAspectSink"
            assert len(plan.lifted_aspects[0].edges) == cross_in_degree
        else:
            assert plan.lifted_aspects == []
            assert plan.warnings != []

    def test_per_entry_min_cross_in_degree_is_independent_per_aspect(self):
        """
        Given: two distinct aspect candidates with two different configured thresholds
        When: build_decoupled_plan runs
        Then: each is evaluated against its OWN threshold, not a shared/global one
        """
        components = {}
        for i in range(6):
            components[f"componentModelSourceA{i}"] = _node(MODEL, to_edges=["componentAspectSinkA"])
        for i in range(12):
            components[f"componentModelSourceB{i}"] = _node(MODEL, to_edges=["componentAspectSinkB"])
        components["componentAspectSinkA"] = _node(INFRA, subcategory="componentsBlockX")
        components["componentAspectSinkB"] = _node(INFRA, subcategory="componentsBlockX")
        components["componentInfraFeeder"] = _node(
            INFRA, to_edges=["componentAspectSinkA", "componentAspectSinkB"], subcategory="componentsBlockX"
        )
        # componentInfraFeeder's edges to the sinks are themselves intra, so the block
        # keeps intra activity regardless of which aspects lift -- isolates D4 from G-O1.
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(
                AspectDecl(id="componentAspectSinkA", min_cross_in_degree=5),  # 6 >= 5: lifts
                AspectDecl(id="componentAspectSinkB", min_cross_in_degree=15),  # 12 < 15: refused
            ),
            concerns=(
                ConcernDecl(
                    label="b flow",
                    edges=tuple((f"componentModelSourceB{i}", "componentAspectSinkB") for i in range(12)),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        lifted_ids = {la.aspect_id for la in plan.lifted_aspects}
        assert lifted_ids == {"componentAspectSinkA"}

    def test_two_aspects_lift_simultaneously_each_with_independent_edge_count(self):
        """
        Given: two distinct, independently-candidate aspects -- each individually
        configured with its own threshold, each with a DIFFERENT cross in-degree,
        BOTH satisfying their own threshold (unlike
        test_per_entry_min_cross_in_degree_is_independent_per_aspect above, which
        has one lift and one refusal)
        When: build_decoupled_plan runs
        Then: both are lifted -- plan.lifted_aspects has exactly 2 entries -- and
        each aspect's `edges` reflects ONLY its own sources, proving no
        cross-contamination between two simultaneously-successful lifts (ADR-036
        D4 admits a second sink by config edit; this closes the gap that no
        existing test builds a plan with two successful lifts at once)
        """
        components = {}
        for i in range(6):
            components[f"componentModelSourceA{i}"] = _node(MODEL, to_edges=["componentAspectSinkA"])
        for i in range(12):
            components[f"componentModelSourceB{i}"] = _node(MODEL, to_edges=["componentAspectSinkB"])
        components["componentAspectSinkA"] = _node(INFRA, subcategory="componentsBlockX")
        components["componentAspectSinkB"] = _node(INFRA, subcategory="componentsBlockX")
        components["componentInfraFeeder"] = _node(
            INFRA, to_edges=["componentAspectSinkA", "componentAspectSinkB"], subcategory="componentsBlockX"
        )
        # componentInfraFeeder's edges to both sinks are themselves intra, so the
        # block keeps intra activity regardless of which/how-many aspects lift --
        # isolates D4 candidacy from G-O1 (block-orphan guard).
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(
                AspectDecl(id="componentAspectSinkA", min_cross_in_degree=5),  # 6 >= 5: lifts
                AspectDecl(id="componentAspectSinkB", min_cross_in_degree=10),  # 12 >= 10: lifts
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)

        assert len(plan.lifted_aspects) == 2
        by_id = {la.aspect_id: la for la in plan.lifted_aspects}
        assert set(by_id) == {"componentAspectSinkA", "componentAspectSinkB"}

        assert len(by_id["componentAspectSinkA"].edges) == 6
        assert {src for src, _tgt in by_id["componentAspectSinkA"].edges} == {
            f"componentModelSourceA{i}" for i in range(6)
        }

        assert len(by_id["componentAspectSinkB"].edges) == 12
        assert {src for src, _tgt in by_id["componentAspectSinkB"].edges} == {
            f"componentModelSourceB{i}" for i in range(12)
        }

    def test_fan_out_source_never_qualifies_regardless_of_cross_degree(self):
        """
        Given: a fan-out source (high cross out-degree, zero cross in-degree) that is
        deliberately configured as an aspect with a trivially low threshold
        When: build_decoupled_plan runs
        Then: it is never lifted -- the sink test (out-degree 0) structurally excludes
        it, no matter how low minCrossInDegree is set (D4: "not a second,
        discretionary test applied per component")
        """
        components = {"componentIdSource": _node(INFRA, to_edges=[f"componentAppTarget{i}" for i in range(20)])}
        for i in range(20):
            components[f"componentAppTarget{i}"] = _node(APP)
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentIdSource", min_cross_in_degree=0),),
            concerns=(
                ConcernDecl(
                    label="id flow",
                    edges=tuple(("componentIdSource", f"componentAppTarget{i}") for i in range(20)),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.lifted_aspects == []
        assert plan.warnings != []


# ============================================================================
# 5. Concern resolution
# ============================================================================


class TestConcernResolution:
    def test_covered_edge_resolves_to_its_configured_label_with_no_warning(self):
        """A single cross edge with exactly one covering concerns entry: clean resolution."""
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(ConcernDecl(label="clean flow", edges=(("componentInfraA", "componentModelA"),)),),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.broadcasts[0].label == "clean flow"
        assert plan.warnings == []

    def test_uncovered_edge_gets_synthesized_fallback_label_and_warning(self):
        """
        Given: a cross edge with NO covering concerns entry
        When: build_decoupled_plan runs
        Then: a fallback label "<srcRoot>→<tgtRoot> flow" is synthesized (G-C3) and a
        warning is recorded. srcRoot/tgtRoot here are the full category ids (D2's
        `root(n) = components[n].category`), matching the Channel key's own src_root/
        tgt_root fields -- NOT the root_slug() port-id abbreviation, since the fallback
        is a human-facing label, and Channel.src_root/tgt_root are the literal category
        values everywhere else in this IR.
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg = EmissionConfig(mode="decoupled", concerns=())
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.broadcasts[0].label == f"{INFRA}→{MODEL} flow"
        assert plan.warnings != []

    def test_double_covered_edge_resolves_lexicographically(self):
        """
        Given: a cross edge named by two concerns entries with different labels
        When: build_decoupled_plan runs
        Then: the lexicographically-first label wins deterministically (G-C4), and a
        warning is recorded
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="beta label", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="alpha label", edges=(("componentInfraA", "componentModelA"),)),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.broadcasts) == 1
        assert plan.broadcasts[0].label == "alpha label"
        assert plan.warnings != []

    def test_double_covered_resolution_is_deterministic_across_declaration_order(self):
        """The lexicographic resolution must not depend on registry declaration order."""
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg_order_1 = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="alpha label", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="beta label", edges=(("componentInfraA", "componentModelA"),)),
            ),
        )
        cfg_order_2 = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="beta label", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="alpha label", edges=(("componentInfraA", "componentModelA"),)),
            ),
        )
        plan_1 = build_decoupled_plan(_forward_map(components), components, cfg_order_1)
        plan_2 = build_decoupled_plan(_forward_map(components), components, cfg_order_2)
        assert plan_1.broadcasts[0].label == plan_2.broadcasts[0].label == "alpha label"


# ============================================================================
# 6. Channel + broadcast keying (D2, D5 fidelity split)
# ============================================================================


class TestChannelAndBroadcastKeying:
    def test_distinct_concerns_over_the_same_cluster_pair_never_merge(self):
        """
        Given: two edges crossing the SAME (srcRoot, tgtRoot) boundary but carrying
        different declared concerns (the D5 "training data" vs "model artifacts"
        fidelity example)
        When: build_decoupled_plan runs
        Then: two separate broadcasts/channels result -- D5's fusion defect
        (subcategory-inferred grouping collapsing distinct payload semantics) is
        structurally impossible because grouping keys off the declared concern, never
        off topology
        """
        components = {
            "componentDataStorage": _node(INFRA, to_edges=["componentModelTrainingTuning"]),
            "componentModelStorage": _node(INFRA, to_edges=["componentModelServing"]),
            "componentModelTrainingTuning": _node(MODEL),
            "componentModelServing": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="training data", edges=(("componentDataStorage", "componentModelTrainingTuning"),)
                ),
                ConcernDecl(label="model artifacts", edges=(("componentModelStorage", "componentModelServing"),)),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        labels = {b.label for b in plan.broadcasts}
        assert labels == {"training data", "model artifacts"}
        assert len(plan.broadcasts) == 2

    def test_same_concern_spanning_multiple_target_roots_merges_into_one_broadcast(self):
        """
        Given: one concern (srcRoot=Infra) whose member edges land in TWO different
        target roots (App and Tools) -- the identity/authz shape
        When: build_decoupled_plan runs
        Then: exactly one broadcast groups both, containing two channels (one per
        tgtRoot), each with its own arm(s) -- broadcasts key by (srcRoot, concern,
        label), channels key by (srcRoot, tgtRoot, concern)
        """
        components = {
            "componentInfraHub": _node(INFRA, to_edges=["componentAppTarget", "componentToolsTarget"]),
            "componentAppTarget": _node(APP),
            "componentToolsTarget": _node(TOOLS),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="shared concern",
                    edges=(
                        ("componentInfraHub", "componentAppTarget"),
                        ("componentInfraHub", "componentToolsTarget"),
                    ),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.broadcasts) == 1
        broadcast = plan.broadcasts[0]
        assert broadcast.arm_count == 2
        assert {c.tgt_root for c in broadcast.channels} == {APP, TOOLS}
        assert all(len(c.arms) == 1 for c in broadcast.channels)


# ============================================================================
# 7. D6 arm splitting
# ============================================================================


class TestArmSplitting:
    def test_single_target_channel_yields_one_arm(self):
        """A channel whose member edges all name the same target lands one arm, full stop."""
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(ConcernDecl(label="single target", edges=(("componentInfraA", "componentModelA"),)),),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.broadcasts[0].channels[0].arms) == 1

    def test_multi_target_channel_splits_one_arm_per_target_no_frequency_bias(self):
        """
        Given: a channel where one target receives 5 member edges and two other
        targets receive 1 edge each
        When: build_decoupled_plan runs
        Then: three arms are produced (one per distinct target) -- edge COUNT per
        target must never influence arm construction; this directly rules out any
        most-frequent-target landing selection (D6: one arm per distinct target)
        """
        # A ComponentNode's to_edges is a flat list, so "5 edges into Dominant" is
        # simulated via five distinct sources feeding the same target -- a single node
        # cannot name the same target twice in one edge list.
        components = {
            "componentInfraHub": _node(INFRA, to_edges=["componentModelMinorA", "componentModelMinorB"]),
            "componentModelDominant": _node(MODEL),
            "componentModelMinorA": _node(MODEL),
            "componentModelMinorB": _node(MODEL),
        }
        for i in range(5):
            components[f"componentInfraFeeder{i}"] = _node(INFRA, to_edges=["componentModelDominant"])
        edges = [(f"componentInfraFeeder{i}", "componentModelDominant") for i in range(5)]
        edges += [
            ("componentInfraHub", "componentModelMinorA"),
            ("componentInfraHub", "componentModelMinorB"),
        ]
        cfg = EmissionConfig(mode="decoupled", concerns=(ConcernDecl(label="fanout", edges=tuple(edges)),))
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.broadcasts) == 1
        channel = plan.broadcasts[0].channels[0]
        targets = {arm.target for arm in channel.arms}
        assert targets == {"componentModelDominant", "componentModelMinorA", "componentModelMinorB"}
        assert len(channel.arms) == 3

    def test_mirrored_cross_cluster_pair_yields_four_ports_and_never_collapses(self):
        """
        Given: a mirrored pair of edges crossing the SAME cluster boundary in both
        directions, each carrying its own distinct concern (the ADR D1 agent-PEP <->
        model-serving inference-pair example)
        When: build_decoupled_plan runs
        Then: two separate broadcasts result (one per direction/concern), each with one
        channel and one arm -- 2 egress + 2 ingress = 4 ports total, and neither
        direction is ever collapsed to `<-->` (D1: the collapse rule is intra-cluster
        only)
        """
        components = {
            "componentModelX": _node(MODEL, to_edges=["componentAppY"]),
            "componentAppY": _node(APP, to_edges=["componentModelX"]),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="request leg", edges=(("componentModelX", "componentAppY"),)),
                ConcernDecl(label="response leg", edges=(("componentAppY", "componentModelX"),)),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert len(plan.broadcasts) == 2
        assert {b.label for b in plan.broadcasts} == {"request leg", "response leg"}
        for broadcast in plan.broadcasts:
            assert len(broadcast.channels) == 1
            assert len(broadcast.channels[0].arms) == 1
        assert plan.collapsed_pairs == []
        assert ("componentModelX", "componentAppY") not in plan.drawn_intra_edges
        assert ("componentAppY", "componentModelX") not in plan.drawn_intra_edges

    def test_target_with_no_intra_in_edges_still_forces_its_own_arm(self):
        """
        Given: a channel target with no intra in-edges at all (the D6
        componentFederationProxy example: "forces a split under any rule")
        When: build_decoupled_plan runs
        Then: it still gets its own arm -- reachability is never a landing mechanism
        """
        components = {
            "componentInfraHub": _node(INFRA, to_edges=["componentToolsIsolated", "componentToolsConnected"]),
            "componentToolsIsolated": _node(TOOLS),  # no intra in-edges from any other Tools node
            "componentToolsConnected": _node(TOOLS, to_edges=[]),
            "componentToolsFeeder": _node(TOOLS, to_edges=["componentToolsConnected"]),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="hub flow",
                    edges=(
                        ("componentInfraHub", "componentToolsIsolated"),
                        ("componentInfraHub", "componentToolsConnected"),
                    ),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        targets = {arm.target for arm in plan.broadcasts[0].channels[0].arms}
        assert targets == {"componentToolsIsolated", "componentToolsConnected"}


# ============================================================================
# 8. PEP wrap -> retarget -> collapse ordering — fixture (b)
# ============================================================================


@pytest.fixture
def pep_mirror_pair_fixture():
    """
    Fixture (b): a PEP node participating in (1) an intra mirror pair with a non-PEP
    partner in the same cluster, and (2) as the landing target of a cross-boundary
    channel. Also includes a second, PEP-free intra mirror pair in the same cluster
    as a collapsing control case, so both outcomes are visible in one fixture.
    """
    components = {
        # Cross source, landing on the PEP.
        "componentInfraSource": _node(INFRA, to_edges=["componentAppTestPolicyEnforcementPoint"]),
        # Intra mirror pair #1: one PEP endpoint -> must wrap+retarget, never collapse.
        "componentAppNonPep": _node(APP, to_edges=["componentAppTestPolicyEnforcementPoint"]),
        "componentAppTestPolicyEnforcementPoint": _node(APP, to_edges=["componentAppNonPep"]),
        # Intra mirror pair #2: neither endpoint is a PEP -> collapses to <-->.
        "componentAppLeaf1": _node(APP, to_edges=["componentAppLeaf2"]),
        "componentAppLeaf2": _node(APP, to_edges=["componentAppLeaf1"]),
    }
    cfg = EmissionConfig(
        mode="decoupled",
        concerns=(
            ConcernDecl(
                label="gate flow",
                edges=(("componentInfraSource", "componentAppTestPolicyEnforcementPoint"),),
            ),
        ),
    )
    return components, cfg


class TestPepWrapRetargetCollapseOrdering:
    def test_pep_gets_a_wrapper(self, pep_mirror_pair_fixture):
        """componentAppTestPolicyEnforcementPoint's id matches the PEP detection regex
        `.*PolicyEnforcementPoint$`; every matching id gets a wrapper universally, with
        no config override, so it must appear in pep_wrappers."""
        components, cfg = pep_mirror_pair_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert "componentAppTestPolicyEnforcementPoint" in plan.pep_wrappers

    def test_pep_involved_mirror_pair_never_collapses(self, pep_mirror_pair_fixture):
        """
        Given: fixture (b)'s pair #1 (componentAppNonPep <-> componentAppTestPolicyEnforcementPoint)
        Then: it is never added to collapsed_pairs (D1: a wrapped endpoint always
        retargets through the wrapper's ports instead of collapsing)
        """
        components, cfg = pep_mirror_pair_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        pair = frozenset({"componentAppNonPep", "componentAppTestPolicyEnforcementPoint"})
        assert not any(frozenset(p) == pair for p in plan.collapsed_pairs)

    def test_pep_free_mirror_pair_collapses(self, pep_mirror_pair_fixture):
        """
        Given: fixture (b)'s pair #2 (componentAppLeaf1 <-> componentAppLeaf2, neither
        endpoint a PEP)
        Then: it IS collapsed -- exactly one entry in collapsed_pairs for this pair,
        proving the ordering (wrap -> retarget -> collapse) only skips collapse for
        pairs actually touching a wrapped node
        """
        components, cfg = pep_mirror_pair_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        pair = frozenset({"componentAppLeaf1", "componentAppLeaf2"})
        assert any(frozenset(p) == pair for p in plan.collapsed_pairs)
        assert plan.collapsed_pair_count == 1

    def test_cross_channel_landing_on_a_pep_retargets_to_wrapper_in_port(self, pep_mirror_pair_fixture):
        """
        Given: the cross channel targeting componentAppTestPolicyEnforcementPoint (a wrapped node)
        When: build_decoupled_plan runs
        Then: the arm's landing_id is the wrapper's in_id, NOT the bare PEP component id
        (D6/D3: "arm lands at the wrapper's `_in` port, not the PEP node itself")
        """
        components, cfg = pep_mirror_pair_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        arm = plan.broadcasts[0].channels[0].arms[0]
        assert arm.target == "componentAppTestPolicyEnforcementPoint"
        wrapper = plan.pep_wrappers["componentAppTestPolicyEnforcementPoint"]
        assert arm.landing_id == wrapper.in_id
        assert arm.landing_id != "componentAppTestPolicyEnforcementPoint"

    def test_intra_edges_touching_the_pep_are_retargeted_through_wrap_ports(self, pep_mirror_pair_fixture):
        """
        Given: fixture (b)'s pair #1 intra edges (both directions between
        componentAppNonPep and componentAppTestPolicyEnforcementPoint)
        Then: both directions are drawn as intra edges (not collapsed), each retargeted
        to reference the wrapper's in_id/out_id rather than the bare PEP id
        """
        components, cfg = pep_mirror_pair_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        wrapper = plan.pep_wrappers["componentAppTestPolicyEnforcementPoint"]
        assert ("componentAppNonPep", wrapper.in_id) in plan.drawn_intra_edges
        assert (wrapper.out_id, "componentAppNonPep") in plan.drawn_intra_edges
        assert ("componentAppNonPep", "componentAppTestPolicyEnforcementPoint") not in plan.drawn_intra_edges
        assert ("componentAppTestPolicyEnforcementPoint", "componentAppNonPep") not in plan.drawn_intra_edges


# ============================================================================
# 9. Aspect + block-orphan guard interaction — fixture (c)
# ============================================================================


@pytest.fixture
def aspect_orphan_violation_fixture():
    """
    Fixture (c): a configured aspect whose block would have zero drawn intra edges if
    the lift proceeded. componentAspectSink and componentBlockSibling share a block
    (subcategory "componentsIsolatedBlock") but have NO intra edge between them or to
    any other block member -- the block is orphaned regardless of the lift decision,
    which is exactly the degenerate case G-O1 exists to catch.
    """
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
            ConcernDecl(
                label="sink flow",
                edges=(
                    ("componentModelSource0", "componentAspectSink"),
                    ("componentModelSource1", "componentAspectSink"),
                    ("componentModelSource2", "componentAspectSink"),
                ),
            ),
            ConcernDecl(label="sibling flow", edges=(("componentBlockSibling", "componentModelElsewhere"),)),
        ),
    )
    return components, cfg


class TestAspectOrphanGuardInteraction:
    def test_lift_is_refused_when_block_would_be_orphaned(self, aspect_orphan_violation_fixture):
        """
        Given: fixture (c) -- candidacy passes (sink, cross-in-degree 3 >= 3) but the
        block-orphan check fails
        When: build_decoupled_plan runs
        Then: the aspect is NOT lifted despite passing the D4 mechanical test
        """
        components, cfg = aspect_orphan_violation_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.lifted_aspects == []

    def test_edges_are_reclassified_as_a_channel_instead(self, aspect_orphan_violation_fixture):
        """The refused edges must still be drawn -- reclassified as their own channel."""
        components, cfg = aspect_orphan_violation_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert any(b.label == "sink flow" and b.arm_count == 1 for b in plan.broadcasts)

    def test_a_loud_warning_is_recorded(self, aspect_orphan_violation_fixture):
        """G-O1 fires with a non-empty warning (message contract tested in guards suite)."""
        components, cfg = aspect_orphan_violation_fixture
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        assert plan.warnings != []


# ============================================================================
# 10. Bands / blocks — moderate depth (shared recipe mechanics)
# ============================================================================


class TestBandsAndBlocks:
    def test_block_entry_exit_detected_by_handling_regex(self):
        """
        Given: a block containing nodes matching `.*InputHandling$` / `.*OutputHandling$`
        When: build_decoupled_plan runs
        Then: the block's entry_id/exit_id are set to those nodes
        """
        components = {
            "componentOrchestrationInputHandling": _node(
                APP, to_edges=["componentOrchestrationCore"], subcategory="componentsOrchestration"
            ),
            "componentOrchestrationCore": _node(
                APP, to_edges=["componentOrchestrationOutputHandling"], subcategory="componentsOrchestration"
            ),
            "componentOrchestrationOutputHandling": _node(APP, subcategory="componentsOrchestration"),
        }
        cfg = EmissionConfig(mode="decoupled")
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        block = plan.clusters[APP].blocks["componentsOrchestration"]
        assert block.entry_id == "componentOrchestrationInputHandling"
        assert block.exit_id == "componentOrchestrationOutputHandling"

    def test_block_without_handling_nodes_has_no_entry_exit(self):
        """A block with no Input/OutputHandling-matching member has entry_id/exit_id None."""
        components = {
            "componentPlainA": _node(INFRA, to_edges=["componentPlainB"], subcategory="componentsPlainBlock"),
            "componentPlainB": _node(INFRA, subcategory="componentsPlainBlock"),
        }
        cfg = EmissionConfig(mode="decoupled")
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        block = plan.clusters[INFRA].blocks["componentsPlainBlock"]
        assert block.entry_id is None
        assert block.exit_id is None

    def test_pure_feeders_and_exit_skips_are_present_and_set_typed(self):
        """
        Given: a block where one member has zero in-block in-degree (a pure feeder)
        Then: pure_feeders/exit_skips are set-like collections and the obvious feeder
        is included -- this is a moderate-depth check only; the exact recipe mechanics
        are shared, not-corpus-specific machinery, so this suite
        does not attempt to pin the full algorithm.
        """
        components = {
            "componentFeederOnly": _node(INFRA, to_edges=["componentMiddle"], subcategory="componentsBlockY"),
            "componentMiddle": _node(INFRA, to_edges=["componentSinkOnly"], subcategory="componentsBlockY"),
            "componentSinkOnly": _node(INFRA, subcategory="componentsBlockY"),
        }
        cfg = EmissionConfig(mode="decoupled")
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        block = plan.clusters[INFRA].blocks["componentsBlockY"]
        assert isinstance(block.pure_feeders, (set, frozenset))
        assert isinstance(block.exit_skips, (set, frozenset))
        assert "componentFeederOnly" in block.pure_feeders

    def test_multiple_egress_ports_sharing_a_root_are_never_chained(self):
        """
        Given: two distinct broadcasts sharing the same src_root (two egress ports in
        one cluster)
        When: build_decoupled_plan runs
        Then: `band_links` contains no pair linking the two egress ports together.

        ADR-036 D1: "band ports are not chained together with invisible ordering
        links" -- a band's own subgraph nesting is what pins its ports to the
        container's edge (ELK's compound-node contiguity constraint), not a chain of
        `~~~` links across the ports. Regression pin against
        `_build_band_links` chaining egress ports together.
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentInfraB": _node(INFRA, to_edges=["componentModelB"]),
            "componentModelA": _node(MODEL),
            "componentModelB": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="concern one", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="concern two", edges=(("componentInfraB", "componentModelB"),)),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        egress_ports = {b.egress_port_id for b in plan.broadcasts}
        assert len(egress_ports) == 2  # sanity: genuinely two distinct egress ports, same root
        for a, b in plan.band_links:
            assert not (a in egress_ports and b in egress_ports), (
                f"egress ports {a!r}/{b!r} are chained together in band_links; ADR-036 D1 "
                "forbids port-to-port chaining"
            )

    def test_multiple_ingress_ports_sharing_a_root_are_never_chained(self):
        """
        Given: a channel with 3 distinct targets landing in the same root (reuses the
        `TestArmSplitting.test_multi_target_channel_splits_one_arm_per_target_no_
        frequency_bias` fixture, which produces exactly 3 ingress ports all in MODEL)
        When: build_decoupled_plan runs
        Then: `band_links` contains no pair linking any two of the resulting ingress
        ports together -- the same ADR-036 D1 rule as the egress case above, applied to
        the ingress side.
        """
        components = {
            "componentInfraHub": _node(INFRA, to_edges=["componentModelMinorA", "componentModelMinorB"]),
            "componentModelDominant": _node(MODEL),
            "componentModelMinorA": _node(MODEL),
            "componentModelMinorB": _node(MODEL),
        }
        for i in range(5):
            components[f"componentInfraFeeder{i}"] = _node(INFRA, to_edges=["componentModelDominant"])
        edges = [(f"componentInfraFeeder{i}", "componentModelDominant") for i in range(5)]
        edges += [
            ("componentInfraHub", "componentModelMinorA"),
            ("componentInfraHub", "componentModelMinorB"),
        ]
        cfg = EmissionConfig(mode="decoupled", concerns=(ConcernDecl(label="fanout", edges=tuple(edges)),))
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        ingress_ports = {arm.port_id for c in plan.broadcasts[0].channels for arm in c.arms}
        assert len(ingress_ports) == 3  # sanity: genuinely three distinct ingress ports, same root
        for a, b in plan.band_links:
            assert not (a in ingress_ports and b in ingress_ports), (
                f"ingress ports {a!r}/{b!r} are chained together in band_links; ADR-036 D1 "
                "forbids port-to-port chaining"
            )


# ============================================================================
# 11. Live-corpus inventory
# ============================================================================


def _expected_broadcast_and_channel_keys(
    cfg: EmissionConfig, components: dict[str, ComponentNode]
) -> tuple[set[tuple[str, str]], set[tuple[str, str, str]], dict[tuple[str, str, str], set[str]]]:
    """
    Independently re-derive the transform's grouping keys straight from the
    registry's own edge declarations (D2: a broadcast is keyed by (srcRoot, concern),
    a channel by (srcRoot, tgtRoot, concern), an arm by the distinct target within a
    channel) -- without calling `build_decoupled_plan()` or reimplementing its D4
    lift/D7 guard/D9 landing/D8 label logic. Used by `TestLiveCorpusInventory` to
    assert the transform's actual output agrees with a figure computed a second,
    independent way, rather than a literal copied from an old corpus snapshot.
    """
    broadcast_keys: set[tuple[str, str]] = set()
    channel_keys: set[tuple[str, str, str]] = set()
    targets_by_channel: dict[tuple[str, str, str], set[str]] = {}
    for decl in cfg.concerns:
        for src, tgt in decl.edges:
            src_root = components[src].category
            tgt_root = components[tgt].category
            broadcast_keys.add((src_root, decl.label))
            channel_key = (src_root, tgt_root, decl.label)
            channel_keys.add(channel_key)
            targets_by_channel.setdefault(channel_key, set()).add(tgt)
    return broadcast_keys, channel_keys, targets_by_channel


def _raw_edge_counts(components: dict[str, ComponentNode], forward_map: dict[str, list[str]]) -> tuple[int, int]:
    """
    Count raw intra/cross edges directly from the corpus by D1's classification rule
    (root(n) = components[n].category) -- the definitional split itself, not any of
    the transform's aspect-lift/channel-grouping/PEP-wrap machinery.
    """
    intra = 0
    cross = 0
    for src, targets in forward_map.items():
        for tgt in targets:
            if components[src].category == components[tgt].category:
                intra += 1
            else:
                cross += 1
    return intra, cross


class TestLiveCorpusInventory:
    """
    Builds the emission.concerns/aspects registry against the real
    risk-map/yaml/components.yaml and asserts the transform's output against figures
    independently re-derived from the raw corpus and from the SHIPPED registry's own
    edge declarations (parsed from the real, committed mermaid-styles.yaml via the
    production parser) -- never a hand-set literal. Every count-shaped assertion below
    is re-derived at test-run time by `_expected_broadcast_and_channel_keys`/
    `_raw_edge_counts` (structural functions over the registry/corpus, independent of
    `build_decoupled_plan()` itself).

    A registry content change (a new component, a new cross edge, an edge
    reassigned to an existing concern label) requires no edit in this class at
    all -- every test below re-derives its own expectation from the shipped
    registry at test-run time, via `live_cfg` below, not from a hand-set
    literal (ADR-036 D12: assigning an edge to an existing label is content,
    reviewed on the `develop` PR, and touches no test file). A NEW label is a
    structural decision and a `main` change to the schema's label `enum`
    (`test_emission_config_schema.py::TestClosedConcernLabelVocabulary`
    pins that every shipped label and the D9 consult set stay within it).
    """

    @pytest.fixture(scope="class")
    @classmethod
    def live_corpus(cls, repo_root: Path):
        components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml").components
        return components, _forward_map(components)

    @pytest.fixture(scope="class")
    @classmethod
    def live_cfg(cls, repo_root: Path) -> EmissionConfig:
        """
        The SHIPPED registry, parsed from the real, committed mermaid-styles.yaml via
        the production parser (`_parse_emission_config`), not a hand-set literal.
        Reading the shipped file directly is what lets every other test in this
        class move with a registry content change without needing anything
        updated here.
        """
        with open(repo_root / "risk-map" / "yaml" / "mermaid-styles.yaml", encoding="utf-8") as fh:
            styles_doc = yaml.safe_load(fh)
        raw_emission = styles_doc.get("graphTypes", {}).get("component", {}).get("emission")
        assert raw_emission is not None, (
            "graphTypes.component.emission is missing from the live mermaid-styles.yaml"
        )
        return _parse_emission_config(raw_emission)

    @pytest.fixture(scope="class")
    @classmethod
    def live_plan(cls, live_corpus, live_cfg):
        components, forward_map = live_corpus
        return build_decoupled_plan(forward_map, components, live_cfg)

    def test_no_warnings_for_the_correctly_specified_registry(self, live_plan):
        """A registry that exactly matches the live corpus produces zero drift warnings."""
        assert live_plan.warnings == []

    def test_broadcast_and_channel_counts_match_the_shipped_registry(self, live_plan, live_corpus, live_cfg):
        """
        Broadcast/channel counts are re-derived from the shipped registry's own edge
        declarations (grouped by (srcRoot, concern) and (srcRoot, tgtRoot, concern)
        respectively) -- never a hand-set literal, so a registry content change that
        keeps the drift guards clean never breaks this test. A broadcast whose concern
        spans N distinct target roots contributes N channels instead of 1.
        """
        components, _forward = live_corpus
        broadcast_keys, channel_keys, _targets = _expected_broadcast_and_channel_keys(live_cfg, components)
        assert len(live_plan.broadcasts) == len(broadcast_keys), (
            f"expected {len(broadcast_keys)} broadcasts (one per distinct (srcRoot, concern) pair "
            f"in the shipped registry); got {len(live_plan.broadcasts)}"
        )
        actual_channels = sum(len(b.channels) for b in live_plan.broadcasts)
        assert actual_channels == len(channel_keys), (
            f"expected {len(channel_keys)} channels (one per distinct (srcRoot, tgtRoot, concern) "
            f"triple in the shipped registry); got {actual_channels}"
        )

    def test_ingress_port_count_matches_the_shipped_registry(self, live_plan, live_corpus, live_cfg):
        """
        Sum of arm_count across all broadcasts equals the number of distinct
        (srcRoot, tgtRoot, concern, target) combinations declared in the shipped
        registry -- computed independently from the registry's edges, not from the
        transform, and never a hand-set literal.
        """
        components, _forward = live_corpus
        _broadcasts, _channels, targets_by_channel = _expected_broadcast_and_channel_keys(live_cfg, components)
        expected_arms = sum(len(targets) for targets in targets_by_channel.values())
        actual_arms = sum(b.arm_count for b in live_plan.broadcasts)
        assert actual_arms == expected_arms, (
            f"expected {expected_arms} total ingress ports (one per distinct target within each "
            f"channel in the shipped registry); got {actual_arms}"
        )

    def test_identity_authz_arms_match_the_shipped_registry(self, live_plan, live_corpus, live_cfg):
        """
        The `identity & authz` broadcast's target set, arm count, and target-root set
        are all derived from the shipped registry's own edge declarations -- never a
        hand-set literal -- so a registry content change (adding a new identity &
        authz edge, or reassigning a component between source and target) moves this
        test with it automatically.
        """
        components, _forward = live_corpus
        _broadcasts, _channels, targets_by_channel = _expected_broadcast_and_channel_keys(live_cfg, components)
        identity_targets: set[str] = set()
        identity_roots: set[str] = set()
        for (src_root, tgt_root, label), targets in targets_by_channel.items():
            if label == "identity & authz":
                identity_targets |= targets
                identity_roots.add(tgt_root)

        broadcast = next(b for b in live_plan.broadcasts if b.label == "identity & authz")
        assert broadcast.arm_count == len(identity_targets), (
            f"expected {len(identity_targets)} arms (one per distinct identity & authz target "
            f"in the shipped registry); got {broadcast.arm_count}"
        )
        assert {c.tgt_root for c in broadcast.channels} == identity_roots

    def test_runtime_hosting_arms_match_the_shipped_registry(self, live_plan, live_corpus, live_cfg):
        """Same derivation as identity & authz above, for the 'runtime hosting' broadcast."""
        components, _forward = live_corpus
        _broadcasts, _channels, targets_by_channel = _expected_broadcast_and_channel_keys(live_cfg, components)
        runtime_targets: set[str] = set()
        runtime_roots: set[str] = set()
        for (src_root, tgt_root, label), targets in targets_by_channel.items():
            if label == "runtime hosting":
                runtime_targets |= targets
                runtime_roots.add(tgt_root)

        broadcast = next(b for b in live_plan.broadcasts if b.label == "runtime hosting")
        assert broadcast.arm_count == len(runtime_targets), (
            f"expected {len(runtime_targets)} arms (one per distinct runtime hosting target "
            f"in the shipped registry); got {broadcast.arm_count}"
        )
        assert {c.tgt_root for c in broadcast.channels} == runtime_roots

    def test_endpoint_enumeration_arm_lands_on_the_component_id_not_the_in_port(
        self, live_plan, live_corpus, live_cfg
    ):
        """
        ADR-030 D14 names `componentToolRegistry -> componentAgentNetworkPolicyEnforcementPoint`
        the caller-side enumerated-endpoint consult; ADR-036 D9 fixes the consult set
        at two labels -- `identity & authz` and this one, `endpoint enumeration` -- and
        a consult-class arm targeting a PEP-wrapped node lands on the component id,
        not the wrapper's `_in` port. The registry hands over the set of endpoints the
        caller may reach; it does not itself pass through the gate. The arm count is
        derived from the shipped registry rather than a hand-set literal.
        """
        components, _forward = live_corpus
        _broadcasts, _channels, targets_by_channel = _expected_broadcast_and_channel_keys(live_cfg, components)
        enumeration_targets: set[str] = set()
        for (src_root, tgt_root, label), targets in targets_by_channel.items():
            if label == "endpoint enumeration":
                enumeration_targets |= targets

        broadcast = next(b for b in live_plan.broadcasts if b.label == "endpoint enumeration")
        assert broadcast.arm_count == len(enumeration_targets), (
            f"expected {len(enumeration_targets)} arms (one per distinct endpoint enumeration "
            f"target in the shipped registry); got {broadcast.arm_count}"
        )
        arm = broadcast.channels[0].arms[0]
        target = "componentAgentNetworkPolicyEnforcementPoint"
        assert arm.target == target
        assert target in live_plan.pep_wrappers, f"{target} is expected to be PEP-wrapped"
        assert arm.landing_id == target, (
            f"expected the endpoint-enumeration consult arm to land on the component id, got {arm.landing_id!r}"
        )

    def test_edge_conservation_matches_plan_derivation(self, live_plan, live_corpus):
        """
        intra_drawn + 2*collapsed + channelled + lifted == total_edges, where the raw
        intra/cross split is computed directly from the corpus (D1's root(n) rule,
        independent of the transform, and never a hand-set literal -- any corpus
        content change moves this split with it) and `collapsed_pair_count`/
        `lifted_count` are read off the plan and cross-checked by their own dedicated
        tests (`test_two_mirror_pairs_collapse_the_rest_do_not`,
        `test_the_audit_record_repository_is_the_sole_lifted_aspect`) rather than
        re-asserted here as bare literals.
        """
        components, forward_map = live_corpus
        raw_intra, raw_cross = _raw_edge_counts(components, forward_map)
        assert raw_intra + raw_cross == live_plan.total_edges

        assert live_plan.intra_drawn_count == raw_intra - 2 * live_plan.collapsed_pair_count
        assert live_plan.channelled_count == raw_cross - live_plan.lifted_count
        assert (
            live_plan.intra_drawn_count
            + 2 * live_plan.collapsed_pair_count
            + live_plan.channelled_count
            + live_plan.lifted_count
            == live_plan.total_edges
        )

    def test_the_audit_record_repository_is_the_sole_lifted_aspect(self, live_plan, live_corpus, live_cfg):
        """
        The property this test pins is "sole lifted aspect, edge count equal to its
        independently-counted cross in-degree" -- the aspect id comes from the shipped
        registry's own `aspects` declaration (never a hand-set literal), and the edge
        count is cross-checked against a direct count of cross edges into it from the
        raw corpus rather than a hardcoded number, so a corpus or registry content
        change that keeps the drift guards clean never breaks this test.
        """
        components, forward_map = live_corpus
        assert len(live_cfg.aspects) == 1, f"expected exactly one declared aspect; got {live_cfg.aspects!r}"
        aspect_id = live_cfg.aspects[0].id
        cross_in_degree = sum(
            1
            for src, targets in forward_map.items()
            for tgt in targets
            if tgt == aspect_id and components[src].category != components[tgt].category
        )

        assert len(live_plan.lifted_aspects) == 1
        lifted = live_plan.lifted_aspects[0]
        assert lifted.aspect_id == aspect_id
        assert len(lifted.edges) == cross_in_degree, (
            f"expected {aspect_id}'s lifted edge count to equal its independently-counted "
            f"cross in-degree ({cross_in_degree}); got {len(lifted.edges)}"
        )

    def test_min_cross_in_degree_threshold_separates_the_sink_from_every_other_node(
        self, live_corpus, live_cfg: EmissionConfig
    ):
        """
        ADR-036 D4: `minCrossInDegree` is a judgment dial, not a tautology -- it must
        sit strictly above every non-candidate's cross in-degree and at or below the
        sink's, so a future second sink must be deliberately admitted by a config
        edit rather than drifting in. Cross in-degree per target is computed directly
        from the raw corpus, independent of `build_decoupled_plan`; the threshold
        comes from the shipped registry (`live_cfg`, parsed via the production
        parser) rather than a hardcoded literal -- a threshold typo in the shipped
        file would otherwise pass this test vacuously against an in-test literal that
        always agreed with itself. Neither the sink's cross in-degree nor the
        runner-up's is a hand-set literal, so this test moves with any corpus or
        registry content change.
        """
        components, forward_map = live_corpus
        cross_in_degree: dict[str, int] = {}
        for src, targets in forward_map.items():
            for tgt in targets:
                if components[src].category != components[tgt].category:
                    cross_in_degree[tgt] = cross_in_degree.get(tgt, 0) + 1

        assert len(live_cfg.aspects) == 1, f"expected exactly one declared aspect; got {live_cfg.aspects!r}"
        aspect = live_cfg.aspects[0]

        other_cross_in_degrees = {node: deg for node, deg in cross_in_degree.items() if node != aspect.id}
        runner_up = max(other_cross_in_degrees.values())
        assert runner_up < aspect.min_cross_in_degree <= cross_in_degree[aspect.id], (
            f"expected the runner-up cross in-degree ({runner_up}) < the declared threshold "
            f"({aspect.min_cross_in_degree}) <= the sink {aspect.id}'s actual cross in-degree "
            f"({cross_in_degree[aspect.id]})"
        )

    def test_pep_wrappers_cover_every_matching_component_id(self, live_plan):
        """
        Every id matching `.*PolicyEnforcementPoint$` in the corpus gets a wrapper,
        universally -- not only ids that happen to sit in a mirror pair (D3: the wrap
        treatment is a generic visual convention for the PEP node type).
        """
        assert set(live_plan.pep_wrappers.keys()) == {
            "componentAgentNetworkPolicyEnforcementPoint",
            "componentApplicationNetworkPolicyEnforcementPoint",
            "componentAuthorizationPolicyEnforcementPoint",
            "componentToolNetworkPolicyEnforcementPoint",
        }

    def test_two_mirror_pairs_collapse_the_rest_do_not(self, live_plan):
        """
        Live corpus has 4 mirrored intra pairs; only the 2 with neither endpoint
        PEP-wrapped collapse (ModelServing<-->TheModel, Tools<-->ToolServer).
        """
        assert live_plan.collapsed_pair_count == 2
        collapsed = {frozenset(p) for p in live_plan.collapsed_pairs}
        assert frozenset({"componentModelServing", "componentTheModel"}) in collapsed
        assert frozenset({"componentTools", "componentToolServer"}) in collapsed

    def test_band_links_are_block_entry_exit_pairs_only_no_port_chains(self, live_plan):
        """
        ADR-036 D1: "Band ports are not chained together with invisible
        ordering links" -- a band's own subgraph nesting is what pins its ports to the
        container's edge (ELK's compound-node contiguity constraint), not a chain of
        `~~~` links across the ports themselves. Only a block's entry->exit pair (one
        link, two real component nodes) is retained.

        This is the corpus-scale regression guard against `_build_band_links`
        producing any port-to-port chain links in the live corpus (each cluster's
        egress ports chained together, each cluster's ingress ports
        chained together) beyond the 4 block entry/exit pairs (Orchestration,
        Application Core, Agent, Tool Input/Output Handling). Pins the
        block-only count (4) so a future change cannot silently reintroduce port
        chaining without this test catching it.
        """
        port_ids = {b.egress_port_id for b in live_plan.broadcasts}
        port_ids |= {arm.port_id for b in live_plan.broadcasts for c in b.channels for arm in c.arms}

        for a, b in live_plan.band_links:
            assert a not in port_ids and b not in port_ids, (
                f"band link ({a}, {b}) chains a port id -- ADR-036 D1 forbids port-to-port chaining"
            )

        expected_block_links = {
            (block.entry_id, block.exit_id)
            for cluster in live_plan.clusters.values()
            for block in cluster.blocks.values()
            if block.entry_id is not None and block.exit_id is not None
        }
        assert set(live_plan.band_links) == expected_block_links
        assert len(live_plan.band_links) == 4


# ============================================================================
# 12. ADR-036 D8: display-layer acronym substitution -- arm-label site
# ("policy enforcement point" -> "PEP", case-insensitive) and its hard invariant
# (port ids stay byte-identical). The node-title site
# (`_decoupled_member_lines`/`_decoupled_pep_wrap_lines`) is covered in
# test_decouple_emitter.py's own D8 section. Implemented in `decouple.py`; the
# port-id assertions in the same tests pin that port ids stay byte-identical
# under D8's label substitution -- the D8 hard invariant.
# ============================================================================


class TestD8ArmLabelSubstitutionLiveCorpus:
    """
    Live-corpus proof of D8's arm-label substitution using the real "identity
    & authz" broadcast -- the corpus's own worked example of a multi-root
    broadcast whose arms land at PEP-wrapped targets (quoted directly from
    ADR-036 D8's own prose: "6 derived arm-label suffixes").

    Port ids captured below are read directly off `build_decoupled_plan()`'s
    output against the real corpus.
    `target_short_name()` always lowercases and space-joins, so every arm
    label already exercises the lowercase-surround case (the Title Case case
    is exercised at the node-title site instead, since it is title-derived,
    not id-derived).
    """

    @pytest.fixture(scope="class")
    @classmethod
    def live_corpus(cls, repo_root: Path):
        components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml").components
        return components, _forward_map(components)

    @pytest.fixture(scope="class")
    @classmethod
    def live_plan(cls, live_corpus):
        components, forward_map = live_corpus
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="identity & authz",
                    edges=(
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentAgentNetworkPolicyEnforcementPoint",
                        ),
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentApplicationNetworkPolicyEnforcementPoint",
                        ),
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentAuthorizationPolicyEnforcementPoint",
                        ),
                        ("componentAuthorizationPolicyDecisionPoint", "componentModelServing"),
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentToolNetworkPolicyEnforcementPoint",
                        ),
                        ("componentIdentityProvider", "componentAgentNetworkPolicyEnforcementPoint"),
                        (
                            "componentIdentityProvider",
                            "componentApplicationNetworkPolicyEnforcementPoint",
                        ),
                        ("componentIdentityProvider", "componentModelServing"),
                        ("componentIdentityProvider", "componentToolNetworkPolicyEnforcementPoint"),
                    ),
                ),
            ),
        )
        return build_decoupled_plan(forward_map, components, cfg)

    def _arms_by_target(self, live_plan):
        broadcast = next(b for b in live_plan.broadcasts if b.label == "identity & authz")
        return {arm.target: arm for c in broadcast.channels for arm in c.arms}

    def test_four_pep_landing_arm_labels_substitute_each_keeping_its_own_prefix(self, live_plan):
        """
        The arm-label half of D8's substitution: each of the 4 PEP-landing arms
        in this broadcast gets its OWN correctly-prefixed substituted label --
        not one generic "PEP" losing "agent network"/"application network"/
        "authorization"/"tool network".
        """
        arms = self._arms_by_target(live_plan)
        expected_labels = {
            "componentAgentNetworkPolicyEnforcementPoint": "identity & authz → agent network PEP",
            "componentApplicationNetworkPolicyEnforcementPoint": "identity & authz → application network PEP",
            "componentAuthorizationPolicyEnforcementPoint": "identity & authz → authorization PEP",
            "componentToolNetworkPolicyEnforcementPoint": "identity & authz → tool network PEP",
        }
        for target, expected_label in expected_labels.items():
            assert arms[target].label == expected_label, (
                f"expected {target}'s arm label {expected_label!r}, got {arms[target].label!r}"
            )

    def test_pep_landing_arm_port_ids_are_byte_identical_to_todays_captured_values(self, live_plan):
        """
        The D8 hard invariant (ADR-036 D8, "The hard invariant" + Follow-up's
        recommended self-check): `port_id` is computed from a SEPARATE
        `target_short_name()` call than `arm_label` (`_build_arms`), so it must
        stay byte-identical regardless of the label substitution.
        These exact strings are captured directly from `build_decoupled_plan()`'s
        output against the real corpus. This test's job is to pin that `port_id`
        stays byte-identical regardless of D8's label substitution.
        """
        arms = self._arms_by_target(live_plan)
        expected_port_ids = {
            "componentAgentNetworkPolicyEnforcementPoint": (
                "p_in_app_identity_authz_agent_network_policy_enforcement_point"
            ),
            "componentApplicationNetworkPolicyEnforcementPoint": (
                "p_in_app_identity_authz_application_network_policy_enforcement_point"
            ),
            "componentAuthorizationPolicyEnforcementPoint": (
                "p_in_tools_identity_authz_authorization_policy_enforcement_point"
            ),
            "componentToolNetworkPolicyEnforcementPoint": (
                "p_in_tools_identity_authz_tool_network_policy_enforcement_point"
            ),
        }
        for target, expected_port_id in expected_port_ids.items():
            assert arms[target].port_id == expected_port_id, (
                f"expected {target}'s port_id to stay byte-identical at {expected_port_id!r} "
                f"(the D8 hard invariant), got {arms[target].port_id!r}"
            )

    def test_non_pep_arms_in_the_same_broadcast_are_unaffected(self, live_plan):
        """
        Regression scope guard: the same broadcast also lands at
        `componentModelServing` (bare arm, no PEP phrase at all) -- it should never
        change, proving the substitution is scoped to labels that actually contain
        the phrase, not applied blanket across every arm in a broadcast that happens
        to have SOME PEP-landing siblings.

        `componentFederationProxy` is category `componentsInfrastructure`, with
        `componentIdentityProvider -> componentFederationProxy` an intra-cluster edge,
        so it is a SOURCE, not a TARGET, of the `identity & authz` broadcast -- it is
        not a target of this broadcast at all and cannot exercise this guard.
        """
        arms = self._arms_by_target(live_plan)
        assert "componentFederationProxy" not in arms, (
            "componentFederationProxy is a source of identity & authz in the live corpus, "
            "not a target -- it should not appear in this broadcast's arm-by-target map"
        )
        assert arms["componentModelServing"].label == "identity & authz"


class TestD8PdpArmLabelNeverAbbreviated:
    """
    Arm-label form: 'policy decision point' -> 'PDP' was evaluated
    alongside PEP and explicitly held out of the D8 set (ADR-036 D8: "its single
    occurrence already fits the wrap target, so it has no measured justification").
    This is the regression guard proving the closed, PEP-only set doesn't
    accidentally generalize to a broader "Policy * Point" pattern: a PDP-named arm
    target sits in the SAME multi-arm channel as a PEP-named one, so a naive regex
    catching both would be caught by this fixture, side by side, in one
    assertion.

    The live corpus has no PDP-landing arm today (`componentAuthorizationPolicy
    DecisionPoint` is only ever a broadcast SOURCE, never a channel target), so
    this is a synthetic fixture -- the live-corpus PDP guard for the node-title
    site lives in test_decouple_emitter.py's `TestD8PdpTitleGuardLiveCorpus`.
    """

    @pytest.fixture
    def mixed_pdp_pep_plan(self):
        components = {
            "componentBroadcastSource": _node(
                INFRA,
                to_edges=[
                    "componentAuthorizationPolicyDecisionPoint",
                    "componentGatewayPolicyEnforcementPoint",
                ],
            ),
            "componentAuthorizationPolicyDecisionPoint": _node(APP),
            "componentGatewayPolicyEnforcementPoint": _node(APP),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="test concern",
                    edges=(
                        ("componentBroadcastSource", "componentAuthorizationPolicyDecisionPoint"),
                        ("componentBroadcastSource", "componentGatewayPolicyEnforcementPoint"),
                    ),
                ),
            ),
        )
        return build_decoupled_plan(_forward_map(components), components, cfg)

    def test_pdp_arm_label_stays_spelled_out_while_pep_arm_label_abbreviates(self, mixed_pdp_pep_plan):
        channel = mixed_pdp_pep_plan.broadcasts[0].channels[0]
        arms_by_target = {arm.target: arm for arm in channel.arms}
        pdp_arm = arms_by_target["componentAuthorizationPolicyDecisionPoint"]
        pep_arm = arms_by_target["componentGatewayPolicyEnforcementPoint"]

        # PDP: unaffected -- explicitly held out of the D8 set.
        assert pdp_arm.label == "test concern → authorization policy decision point"
        # PEP: substituted per D8 -- proves this fixture would genuinely catch a
        # naive "Policy * Point" pattern that wrongly abbreviated both, since PDP
        # is asserted unchanged in the SAME assertion pass.
        assert pep_arm.label == "test concern → gateway PEP"


# ============================================================================
# 13. ADR-036 D9: consult-class channel landing. An arm whose concern is in the
# emitter's closed consult-class set lands on the target's COMPONENT id even when
# the target is PEP-wrapped; every other arm keeps D3's `_in`-port landing. The
# rule touches `Arm.landing_id` only -- `port_id` and `label` are computed from
# separate expressions and must stay byte-identical either way.
# ============================================================================


class TestD9ConsultVsDataLandingSideBySide:
    """
    The discriminating fixture: ONE PEP-wrapped target reached by FOUR channels
    that differ only in concern -- one consult-class, one plainly data-class, and
    two near-miss labels chosen to break a substring/regex classifier in each
    direction. A landing rule that ignored the concern (never retargeting, or
    always retargeting) fails one half of every assertion pass below, side by side;
    a rule that matched loosely fails the near-miss test.

    `identity & authz` is used as the consult-class label because it is the
    emitter's declared consult-class concern; the data-class partner labels are
    arbitrary, which is the point (everything not in the closed set is data).
    """

    @pytest.fixture
    def two_concern_plan(self):
        components = {
            "componentConsultSource": _node(INFRA, to_edges=["componentAppGatePolicyEnforcementPoint"]),
            "componentDataSource": _node(MODEL, to_edges=["componentAppGatePolicyEnforcementPoint"]),
            # Near-miss sources: their labels sit on either side of a containment
            # relation with the consult label (see the near-miss test's docstring).
            "componentSupersetSource": _node(INFRA, to_edges=["componentAppGatePolicyEnforcementPoint"]),
            "componentSubsetSource": _node(MODEL, to_edges=["componentAppGatePolicyEnforcementPoint"]),
            "componentAppGatePolicyEnforcementPoint": _node(APP),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="identity & authz",
                    edges=(("componentConsultSource", "componentAppGatePolicyEnforcementPoint"),),
                ),
                ConcernDecl(
                    label="request flow",
                    edges=(("componentDataSource", "componentAppGatePolicyEnforcementPoint"),),
                ),
                ConcernDecl(
                    label="identity & authz posture",
                    edges=(("componentSupersetSource", "componentAppGatePolicyEnforcementPoint"),),
                ),
                ConcernDecl(
                    label="authz",
                    edges=(("componentSubsetSource", "componentAppGatePolicyEnforcementPoint"),),
                ),
            ),
        )
        return build_decoupled_plan(_forward_map(components), components, cfg)

    def _arm_for(self, plan, concern: str):
        return next(
            arm
            for broadcast in plan.broadcasts
            for channel in broadcast.channels
            if channel.concern == concern
            for arm in channel.arms
        )

    def test_consult_arm_lands_on_the_component_not_the_in_port(self, two_concern_plan):
        """
        Given: a consult-class channel landing at a PEP-wrapped node
        Then: landing_id is the bare component id -- the verdict is consumed BY the
        enforcement point, it does not traverse the gate to a destination (D9)
        """
        arm = self._arm_for(two_concern_plan, "identity & authz")
        wrapper = two_concern_plan.pep_wrappers["componentAppGatePolicyEnforcementPoint"]
        assert arm.target == "componentAppGatePolicyEnforcementPoint"
        assert arm.landing_id == "componentAppGatePolicyEnforcementPoint"
        assert arm.landing_id != wrapper.in_id

    def test_data_arm_to_the_same_target_still_lands_on_the_in_port(self, two_concern_plan):
        """
        The control half: same wrapped target, non-consult concern. Proves D9 is
        scoped to the consult set rather than having removed `_in` landing wholesale
        (D3: traffic must visibly enter through the enforcement point).
        """
        arm = self._arm_for(two_concern_plan, "request flow")
        wrapper = two_concern_plan.pep_wrappers["componentAppGatePolicyEnforcementPoint"]
        assert arm.target == "componentAppGatePolicyEnforcementPoint"
        assert arm.landing_id == wrapper.in_id

    def test_near_miss_labels_are_data_class_in_both_containment_directions(self, two_concern_plan):
        """
        D9 specifies a closed SET of labels, matched exactly -- not a substring,
        prefix, or regex test. Two near-miss labels pin that in both directions,
        since a loose classifier fails in only one of them:

          - "identity & authz posture" CONTAINS the consult label, so a
            `CONSULT_LABEL in label` mutant would wrongly route it as consult;
          - "authz" is CONTAINED BY the consult label, so a `label in CONSULT_LABEL`
            (or a bare "authz" keyword) mutant would do the same.

        Both must land on `_in` like any other data-class concern. Without this
        test the exact-match discipline rests on reading the implementation rather
        than on an assertion, since the two original labels in this fixture share
        no substring relation at all.
        """
        wrapper = two_concern_plan.pep_wrappers["componentAppGatePolicyEnforcementPoint"]
        for label in ("identity & authz posture", "authz"):
            arm = self._arm_for(two_concern_plan, label)
            assert arm.target == "componentAppGatePolicyEnforcementPoint"
            assert arm.landing_id == wrapper.in_id, (
                f"near-miss label {label!r} is not in the closed consult set and must "
                f"keep its `_in` landing; got {arm.landing_id!r}"
            )

    def test_port_id_and_label_are_identical_across_the_two_classes(self, two_concern_plan):
        """
        D9's stated invariant: the classification changes the landing site only.
        Both arms name the same single target, so both are bare (D6 single-arm) and
        their id/label grammar must be indistinguishable -- only `landing_id` differs.
        """
        consult = self._arm_for(two_concern_plan, "identity & authz")
        data = self._arm_for(two_concern_plan, "request flow")
        assert consult.port_id == "p_in_app_identity_authz"
        assert data.port_id == "p_in_app_request_flow"
        assert consult.label == "identity & authz"
        assert data.label == "request flow"


class TestD9ConsultLandingScope:
    def test_consult_arm_to_an_unwrapped_target_is_unchanged(self):
        """
        D9 only ever removes an `_in` retarget; a consult arm landing at a node that
        was never wrapped already lands on the component id and must stay there.
        """
        components = {
            "componentConsultSource": _node(INFRA, to_edges=["componentAppPlainNode"]),
            "componentAppPlainNode": _node(APP),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="identity & authz",
                    edges=(("componentConsultSource", "componentAppPlainNode"),),
                ),
            ),
        )
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        arm = plan.broadcasts[0].channels[0].arms[0]
        assert "componentAppPlainNode" not in plan.pep_wrappers
        assert arm.landing_id == "componentAppPlainNode"

    def test_intra_edges_into_a_wrapped_pep_still_retarget_through_the_in_port(self):
        """
        Scope guard: D9 is a CHANNEL-landing rule. The separate intra-edge
        wrap->retarget path (`_process_intra_edges`, D1) is untouched, so an
        intra edge into a wrapped PEP still enters through `_in` regardless of any
        concern label -- concerns only ever apply to cross edges.
        """
        components = {
            "componentAppNeighbour": _node(APP, to_edges=["componentAppGatePolicyEnforcementPoint"]),
            "componentAppGatePolicyEnforcementPoint": _node(APP),
        }
        cfg = EmissionConfig(mode="decoupled")
        plan = build_decoupled_plan(_forward_map(components), components, cfg)
        wrapper = plan.pep_wrappers["componentAppGatePolicyEnforcementPoint"]
        assert ("componentAppNeighbour", wrapper.in_id) in plan.drawn_intra_edges


class TestD9ConsultLandingLiveCorpus:
    """
    The live-corpus half: against the real `emission.concerns` registry, exactly the
    four `identity & authz` arms that target a PEP-wrapped node move to their
    component ids, and the one that does not target a wrapper is untouched.

    Reuses the same 9-edge `identity & authz` registry entry as
    `TestD8ArmLabelSubstitutionLiveCorpus`; the four wrapped targets among its nine
    edges are read off `build_decoupled_plan()` against the real corpus.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def live_plan(cls, repo_root: Path):
        components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml").components
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="identity & authz",
                    edges=(
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentAgentNetworkPolicyEnforcementPoint",
                        ),
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentApplicationNetworkPolicyEnforcementPoint",
                        ),
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentAuthorizationPolicyEnforcementPoint",
                        ),
                        ("componentAuthorizationPolicyDecisionPoint", "componentModelServing"),
                        (
                            "componentAuthorizationPolicyDecisionPoint",
                            "componentToolNetworkPolicyEnforcementPoint",
                        ),
                        ("componentIdentityProvider", "componentAgentNetworkPolicyEnforcementPoint"),
                        (
                            "componentIdentityProvider",
                            "componentApplicationNetworkPolicyEnforcementPoint",
                        ),
                        ("componentIdentityProvider", "componentModelServing"),
                        (
                            "componentIdentityProvider",
                            "componentToolNetworkPolicyEnforcementPoint",
                        ),
                    ),
                ),
            ),
        )
        return build_decoupled_plan(_forward_map(components), components, cfg)

    def _arms_by_target(self, live_plan):
        broadcast = next(b for b in live_plan.broadcasts if b.label == "identity & authz")
        return {arm.target: arm for c in broadcast.channels for arm in c.arms}

    def test_all_four_wrapped_consult_targets_land_on_their_component_ids(self, live_plan):
        arms = self._arms_by_target(live_plan)
        wrapped_targets = [
            "componentAgentNetworkPolicyEnforcementPoint",
            "componentApplicationNetworkPolicyEnforcementPoint",
            "componentAuthorizationPolicyEnforcementPoint",
            "componentToolNetworkPolicyEnforcementPoint",
        ]
        for target in wrapped_targets:
            assert target in live_plan.pep_wrappers, f"{target} is expected to be PEP-wrapped"
            assert arms[target].landing_id == target, (
                f"expected {target}'s consult arm to land on the component id, got {arms[target].landing_id!r}"
            )

    def test_consult_arm_to_an_unwrapped_target_keeps_its_landing(self, live_plan):
        """
        D9's classifier is concern-keyed, so it marks the `componentModelServing`
        arm consult-class the same as its four PEP-wrapped siblings -- but the
        landing RULE only moves an arm whose target is PEP-wrapped (D9: "a
        consult-class channel arm whose target is a PEP-wrapped node lands on the
        component id"). `componentModelServing` is never wrapped, so its landing
        is identical to what a data-class arm to
        the same unwrapped target would produce.

        `componentFederationProxy` is not a target of this broadcast at all: it
        is a source, not a target, of `identity & authz`, since its category is
        `componentsInfrastructure` (intra-cluster with `componentIdentityProvider`),
        so there is only one unwrapped target left to exercise this guard.
        """
        arms = self._arms_by_target(live_plan)
        assert "componentFederationProxy" not in arms, (
            "componentFederationProxy is a source of identity & authz in the live corpus, not a target"
        )
        assert arms["componentModelServing"].landing_id == "componentModelServing"

    def test_consult_arm_port_ids_stay_byte_identical(self, live_plan):
        """
        D9's landing-only invariant against the live corpus: these are the same four
        port ids `TestD8ArmLabelSubstitutionLiveCorpus` pins, unchanged by the
        landing reclassification (D7 content-derived id stability).
        """
        arms = self._arms_by_target(live_plan)
        expected_port_ids = {
            "componentAgentNetworkPolicyEnforcementPoint": (
                "p_in_app_identity_authz_agent_network_policy_enforcement_point"
            ),
            "componentApplicationNetworkPolicyEnforcementPoint": (
                "p_in_app_identity_authz_application_network_policy_enforcement_point"
            ),
            "componentAuthorizationPolicyEnforcementPoint": (
                "p_in_tools_identity_authz_authorization_policy_enforcement_point"
            ),
            "componentToolNetworkPolicyEnforcementPoint": (
                "p_in_tools_identity_authz_tool_network_policy_enforcement_point"
            ),
        }
        for target, expected_port_id in expected_port_ids.items():
            assert arms[target].port_id == expected_port_id


"""
Test Summary
============
Total test functions: 83 (across 19 test classes + 3 pytest fixtures used as synthetic
corpora)

Coverage areas:
- Grammar primitives (slug/root_slug/target_short_name/pep_wrap_base): 17 tests, all
  exact-literal, including both ADR-quoted slug() examples.
- ADR D6 worked-example reproduction (port ids + arm labels, literal strings): 6 tests.
- Partition + basic pipeline (fixture a): 5 tests.
- Aspect candidacy (D4): 7 tests (sink test, threshold boundary x3, per-entry
  independence (one lift/one refusal), two-simultaneous-lift independence,
  source-exclusion).
- Concern resolution: 4 tests (covered, uncovered+fallback, double-covered, order
  independence).
- Channel/broadcast keying: 2 tests (anti-fusion, broadcast merge across target roots).
- D6 arm splitting: 4 tests (single-target, multi-target no-frequency-bias, mirrored
  cross pair 4-ports-no-collapse, no-intra-in-edges-still-splits).
- PEP wrap/retarget/collapse ordering (fixture b): 5 tests.
- Aspect + block-orphan guard interaction (fixture c): 3 tests.
- Bands/blocks (moderate depth): 5 tests (entry/exit detection, no-entry/exit,
  pure-feeders/exit-skips, plus two ADR-036 D1 band-ports-not-chained regression
  tests -- multi-egress-port and multi-ingress-port fixtures proving `band_links`
  never chains two ports sharing a root).
- Live-corpus inventory (independently re-verified numbers): 12 tests
  (includes one ADR-036 D1 regression guard pinning `band_links` to exactly the 4
  block entry/exit pairs, zero port-to-port chain links; and
  one ADR-036 D9 / ADR-030 D14 landing check for the `endpoint enumeration` consult
  arm).
- ADR-036 D8 (display-layer acronym substitution, arm-label site): 4 tests across 2
  classes. `TestD8ArmLabelSubstitutionLiveCorpus` -- the real "identity & authz"
  broadcast's 4 PEP-landing arms substitute to "PEP", each keeping its own prefix
  (1 test); the port ids computed from those same targets stay byte-identical
  (1 regression pin, the D8 hard invariant); the broadcast's 2 non-PEP
  arms are unaffected (1 scope guard). `TestD8PdpArmLabelNeverAbbreviated`
  -- a synthetic PDP+PEP mixed channel, PDP unchanged/PEP substituted in the same
  assertion pass (1 test). Node-title-site D8 coverage
  (`_decoupled_member_lines`/`_decoupled_pep_wrap_lines`) lives in
  test_decouple_emitter.py instead -- this file covers only `decouple.py`'s
  `_build_arms`/`arm_label` site plus the port-id invariant.
- ADR-036 D9 (consult-class channel landing): 9 tests across 3 classes.
  `TestD9ConsultVsDataLandingSideBySide` -- one PEP-wrapped target, four channels
  differing only in concern, so a rule that ignored the concern in either direction
  fails half of every pass (4 tests, including the port-id/label invariant and a
  near-miss-label pair designed to catch a substring classifier -- one that matches
  a label as a substring of another rather than exactly -- in either containment
  direction).
  `TestD9ConsultLandingScope` -- a consult arm to an unwrapped target is unchanged,
  and the separate intra-edge wrap->retarget path is untouched (2 tests).
  `TestD9ConsultLandingLiveCorpus` -- the real registry's four wrapped
  `identity & authz` targets land on their component ids, its two unwrapped arms are
  unaffected, and the four port ids stay byte-identical (3 tests). The fifth
  consult-class arm -- the registry's enumerated-endpoint consult onto the agent
  network PEP (ADR-030 D14), labelled `endpoint enumeration` -- is pinned separately
  in `TestLiveCorpusInventory` below, since it needs the full 12-concern registry
  rather than this class's 9-edge `identity & authz`-only fixture. The data-class
  half against the live corpus (`tool calls`, both `inference / serving` arms
  staying on `_in`) lives in test_decouple_emitter.py, which already has the full
  12-concern live registry.

Scope notes:
- Two design decisions are documented inline at their point of use:
  1. The G-C3 synthesized fallback label uses the FULL category id for srcRoot/tgtRoot
     (`componentsInfrastructure→componentsModel flow`), not root_slug() -- see comment
     in test_uncovered_edge_gets_synthesized_fallback_label_and_warning.
  2. PEP wrap id/in-id/out-id base abbreviation ("PolicyEnforcementPoint" -> "Pep") is
     derived from the single literal example in pep_wrap_base()'s own docstring and
     generalized across all PEP ids -- see TestPepWrapBaseGrammar.
"""
