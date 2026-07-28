#!/usr/bin/env python3
"""
Tests for the decoupled component-graph transform (ADR-036, `graphing/decouple.py`).

`graphing/decouple.py` implements this contract against ADR-036 D1-D7. This suite was
the RED phase of the TDD chain (Phase 1, task 1.1); it is retained as the regression
pin against the now-GREEN implementation.

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
`tgt_root` store; `root_slug()` is the separate, ID-grammar-only abbreviation (D6/§E: "infra",
"model", "app", "tools") used solely to build port ids. Tests below exercise both and never
conflate them.

Test Coverage
=============
1. Grammar primitives (§E): slug(), root_slug(), target_short_name(), pep_wrap_base() —
   exact literal assertions, including the two ADR-quoted slug() edge cases.
2. Port-id / arm-label grammar reproduced from the ADR D6 runtime-hosting worked example
   (literal ids quoted directly from docs/adr/036-decoupled-component-graph-emission.md).
3. Partition (D2): intra vs cross classification by root(n), via the minimal 2-cluster
   single-broadcast fixture (fixture a).
4. Aspect candidacy (D4): sink test, cross-in-degree threshold boundary, per-entry
   threshold, source-exclusion.
5. Concern resolution (§B step 3): covered, uncovered (fallback + warning), double-covered
   (lexicographic resolution + warning).
6. Channel + broadcast keying (D2, D5/R5): grouping by (srcRoot, tgtRoot, concern) and
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
    (moderate depth, per plan §B step 7 — this is shared "recipe mechanics", not
    corpus-specific judgment, so exhaustive coverage is not required here).
11. Live-corpus inventory: `build_decoupled_plan()` against the real
    `risk-map/yaml/components.yaml`, asserting the plan §C numbers this suite's author
    independently re-derived from the corpus.
12. ADR-036 D8 (display-layer acronym substitution, arm-label site): the real
    "identity & authz" broadcast's 4 PEP-landing arm labels substitute to "PEP",
    each keeping its own distinguishing prefix; the port ids computed from those
    same targets stay byte-identical (the D8 hard invariant); a synthetic PDP+PEP
    mixed channel proves the closed set doesn't generalize to PDP.

Everything here is written against the *final* ADR-036 rules, not the bake-off
prototypes reconciled away in the plan's §R ledger. In particular:
  - No landing selection exists anywhere in this suite (R1/R2/R4): a channel with N
    distinct targets always produces N arms.
  - No `forceSplit` / override key of any kind is referenced (R3/R7/R11).
  - The aspect `minCrossInDegree` threshold used throughout is 10, not 5 (D4/R6).
"""

import sys
from pathlib import Path

import pytest

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
# 1. Grammar primitives (§E)
# ============================================================================


class TestSlugGrammar:
    """
    slug(): lowercase, '&' dropped (not underscored), non-alphanumeric runs -> single
    '_', trimmed. Both literal examples are quoted directly from plan §E.
    """

    def test_slug_drops_ampersand_identity_authz(self):
        """
        Given: the exact ADR/plan §E example "identity & authz"
        When: slug() is called
        Then: '&' is dropped entirely (not replaced with '_'), yielding "identity_authz"
        """
        assert slug("identity & authz") == "identity_authz"

    def test_slug_collapses_slash_run_inference_serving(self):
        """
        Given: the exact ADR/plan §E example "inference / serving"
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
        Given: the "app + agent egress" concern label (emission.concerns entry #10, §C)
        When: slug() is called
        Then: '+' is not dropped (only '&' is dropped per §E) — it is swept into the
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
        Then: falls back to lowercase of the id minus the 'components' prefix (§E fallback rule)
        """
        assert root_slug("componentsGovernance") == "governance"


class TestTargetShortNameGrammar:
    """
    target_short_name(): component id minus 'component' prefix, camel-split, lowercased,
    space-joined — id-derived, not title-derived (§E). Per plan §Q7, this is the FULL
    uncompressed name (e.g. "authorization policy enforcement point"), not the informal
    ADR-prose abbreviations like "AuthzPEP" — those are shorthand in prose only, and the
    ADR itself names this verbosity as an accepted, known cost (§Q7).
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
        (per §Q7: verbosity is an accepted cost, not a rule this function works around)
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
    The one literal example in plan §E ("agentNetworkPep_wrap") fixes the "PolicyEnforcementPoint"
    -> "Pep" abbreviation; in_id/out_id/wrap_id are then `<base>_in` / `<base>_out` / `<base>_wrap`.
    """

    def test_pep_wrap_base_matches_the_quoted_plan_example(self):
        """
        Given: the exact component id used in plan §E's wrap-id example
        When: pep_wrap_base() is called
        Then: returns "agentNetworkPep" (so wrap_id becomes "agentNetworkPep_wrap",
        the literal string quoted in the plan)
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
        D4 explicitly anticipates "a future second sink" being deliberately
        admitted; this closes the gap that no existing test builds a plan with two
        successful lifts at once)
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
        adversarially configured as an aspect with a trivially low threshold
        When: build_decoupled_plan runs
        Then: it is never lifted -- the sink test (out-degree 0) structurally excludes
        it, no matter how low minCrossInDegree is set (D4: "structurally impossible",
        not a discretionary per-component judgment)
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
# 5. Concern resolution (§B step 3)
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
# 6. Channel + broadcast keying (D2, D5/R5 anti-fusion)
# ============================================================================


class TestChannelAndBroadcastKeying:
    def test_distinct_concerns_over_the_same_cluster_pair_never_merge(self):
        """
        Given: two edges crossing the SAME (srcRoot, tgtRoot) boundary but carrying
        different declared concerns (the D5 "training data" vs "model artifacts"
        fidelity example)
        When: build_decoupled_plan runs
        Then: two separate broadcasts/channels result -- R5's fusion defect
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
        most-frequent-target landing selection (R1)
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
        `.*PolicyEnforcementPoint$` (§B step 6; no config override, per plan §Q5), so it
        must appear in pep_wrappers."""
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
# 10. Bands / blocks — moderate depth (shared recipe mechanics, per plan §B step 7)
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
        are shared, not-corpus-specific machinery per plan §B step 7, so this suite
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

        ADR-036 D1's "band ports are not chained together with invisible ordering
        links" revision: a band's own subgraph nesting is what pins its ports to the
        container's edge (ELK's compound-node contiguity constraint) -- chaining the
        ports with `~~~` links was found to actively cause horizontal sprawl (ELK's
        `INCLUDE_CHILDREN` hierarchy handling overrides the nested subgraph's own
        layout direction whenever a boundary-crossing edge, which every port carries
        by definition, touches it) and is removed entirely. Was RED against
        `_build_band_links` before it stopped chaining egress ports together; now
        GREEN and retained as the regression pin.
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
                f"egress ports {a!r}/{b!r} are chained together in band_links; port-to-port "
                "chaining is removed by the ADR-036 D1 band-ports-not-chained revision"
            )

    def test_multiple_ingress_ports_sharing_a_root_are_never_chained(self):
        """
        Given: a channel with 3 distinct targets landing in the same root (reuses the
        `TestArmSplitting.test_multi_target_channel_splits_one_arm_per_target_no_
        frequency_bias` fixture, which produces exactly 3 ingress ports all in MODEL)
        When: build_decoupled_plan runs
        Then: `band_links` contains no pair linking any two of the resulting ingress
        ports together -- the same D1 revision as the egress case above, applied to
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
                f"ingress ports {a!r}/{b!r} are chained together in band_links; port-to-port "
                "chaining is removed by the ADR-036 D1 band-ports-not-chained revision"
            )


# ============================================================================
# 11. Live-corpus inventory (plan §C)
# ============================================================================


class TestLiveCorpusInventory:
    """
    Builds the emission.concerns/aspects registry exactly as specified in plan §C,
    against the real risk-map/yaml/components.yaml, and asserts the plan's numbers.

    These numbers were independently re-derived from the live corpus while writing
    this suite, not copied blind from the plan. They are exact-today assertions;
    corpus drift is caught by the drift guards (test_decouple_guards.py), not by
    this test re-deriving anything.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def live_corpus(cls, repo_root: Path):
        components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml")
        return components, _forward_map(components)

    @pytest.fixture(scope="class")
    @classmethod
    def live_plan(cls, live_corpus):
        components, forward_map = live_corpus
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentSecureLogging", min_cross_in_degree=10),),
            concerns=(
                ConcernDecl(
                    label="model artifacts",
                    edges=(
                        ("componentModelStorage", "componentModelServing"),
                        ("componentModelRegistry", "componentModelServing"),
                    ),
                ),
                ConcernDecl(
                    label="training data",
                    edges=(("componentDataStorage", "componentModelTrainingTuning"),),
                ),
                ConcernDecl(
                    label="runtime hosting",
                    edges=(
                        ("componentRuntimeHosting", "componentModelServing"),
                        ("componentRuntimeHosting", "componentApplication"),
                        ("componentRuntimeHosting", "componentReasoningCore"),
                    ),
                ),
                ConcernDecl(label="tool hosting", edges=(("componentToolHosting", "componentToolServer"),)),
                ConcernDecl(
                    label="tool discovery",
                    edges=(("componentToolRegistry", "componentToolNetworkPolicyEnforcementPoint"),),
                ),
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
                        ("componentIdentityProvider", "componentFederationProxy"),
                        ("componentIdentityProvider", "componentModelServing"),
                        ("componentIdentityProvider", "componentToolNetworkPolicyEnforcementPoint"),
                    ),
                ),
                ConcernDecl(
                    label="model publish",
                    edges=(("componentModelTrainingTuning", "componentModelRegistry"),),
                ),
                ConcernDecl(
                    label="inference / serving",
                    edges=(
                        ("componentModelServing", "componentAgentNetworkPolicyEnforcementPoint"),
                        ("componentModelServing", "componentApplicationNetworkPolicyEnforcementPoint"),
                    ),
                ),
                ConcernDecl(
                    label="tool calls",
                    edges=(("componentAgentToolTransport", "componentToolNetworkPolicyEnforcementPoint"),),
                ),
                ConcernDecl(
                    label="app + agent egress",
                    edges=(
                        ("componentAgentNetworkPolicyEnforcementPoint", "componentModelServing"),
                        ("componentApplicationNetworkPolicyEnforcementPoint", "componentModelServing"),
                    ),
                ),
                ConcernDecl(label="tool registration", edges=(("componentTools", "componentToolRegistry"),)),
                ConcernDecl(
                    label="tool results",
                    edges=(("componentToolNetworkPolicyEnforcementPoint", "componentAgentToolTransport"),),
                ),
            ),
        )
        components, forward_map = live_corpus
        return build_decoupled_plan(forward_map, components, cfg)

    def test_no_warnings_for_the_correctly_specified_registry(self, live_plan):
        """A registry that exactly matches the live corpus produces zero drift warnings."""
        assert live_plan.warnings == []

    def test_twelve_broadcasts_fifteen_channels(self, live_plan):
        """
        12 concerns entries => 12 broadcasts; 'runtime hosting' and 'identity & authz'
        each span 2 and 3 distinct target roots respectively, contributing 2 and 3
        channels instead of 1 -- 10 single-channel broadcasts + 2 + 3 = 15 channels.
        """
        assert len(live_plan.broadcasts) == 12
        total_channels = sum(len(b.channels) for b in live_plan.broadcasts)
        assert total_channels == 15

    def test_twenty_ingress_ports_total(self, live_plan):
        """Sum of arm_count across all broadcasts is 20 (Infra 2, Model 5, App 7, Tools 6)."""
        assert sum(b.arm_count for b in live_plan.broadcasts) == 20

    def test_identity_authz_is_six_arms(self, live_plan):
        broadcast = next(b for b in live_plan.broadcasts if b.label == "identity & authz")
        assert broadcast.arm_count == 6
        assert {c.tgt_root for c in broadcast.channels} == {MODEL, APP, TOOLS}

    def test_runtime_hosting_is_three_arms(self, live_plan):
        broadcast = next(b for b in live_plan.broadcasts if b.label == "runtime hosting")
        assert broadcast.arm_count == 3
        assert {c.tgt_root for c in broadcast.channels} == {MODEL, APP}

    def test_edge_conservation_matches_plan_derivation(self, live_plan):
        """43 intra-drawn + 2*2 collapsed + 26 channelled + 17 lifted == 90 total edges.

        The intra-drawn and total counts dropped by one when the authorization PEP
        moved in-flow upstream of the tool server: two tool-tier edges were replaced
        by one. Both replaced and replacement edges are intra-tools, so the cross-edge
        split (26 channelled + 17 lifted) is unchanged.
        """
        assert live_plan.intra_drawn_count == 43
        assert live_plan.collapsed_pair_count == 2
        assert live_plan.channelled_count == 26
        assert live_plan.lifted_count == 17
        assert live_plan.total_edges == 90
        assert (
            live_plan.intra_drawn_count
            + 2 * live_plan.collapsed_pair_count
            + live_plan.channelled_count
            + live_plan.lifted_count
            == live_plan.total_edges
        )

    def test_secure_logging_is_the_sole_lifted_aspect_with_seventeen_edges(self, live_plan):
        assert len(live_plan.lifted_aspects) == 1
        lifted = live_plan.lifted_aspects[0]
        assert lifted.aspect_id == "componentSecureLogging"
        assert len(lifted.edges) == 17

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
        Live corpus has 5 mirrored intra pairs; only the 2 with neither endpoint
        PEP-wrapped collapse (ModelServing<-->TheModel, Tools<-->ToolServer).
        """
        assert live_plan.collapsed_pair_count == 2
        collapsed = {frozenset(p) for p in live_plan.collapsed_pairs}
        assert frozenset({"componentModelServing", "componentTheModel"}) in collapsed
        assert frozenset({"componentTools", "componentToolServer"}) in collapsed

    def test_band_links_are_block_entry_exit_pairs_only_no_port_chains(self, live_plan):
        """
        ADR-036 D1 revision ("Band ports are not chained together with invisible
        ordering links"): a band's own subgraph nesting is what pins its ports to the
        container's edge (ELK's compound-node contiguity constraint), not a chain of
        `~~~` links across the ports themselves -- a hands-on render-verification pass
        found the chain links actively caused horizontal sprawl (every port carries a
        boundary-crossing edge, which makes ELK stamp `INCLUDE_CHILDREN` hierarchy
        handling on it, silently overriding the nested subgraph's own layout
        direction). Only a block's entry->exit pair (one link, two real component
        nodes) is small enough that the same failure mode does not apply, and is
        retained.

        This is the corpus-scale regression guard: was RED against
        `_build_band_links` before the fix, which produced 28 band links in the
        live corpus -- 24 port-to-port chain links (each cluster's egress ports
        chained together, each cluster's ingress ports chained together) plus the
        4 block entry/exit pairs (Orchestration, Application Core, Agent, Tool
        Input/Output Handling). Now GREEN; pins the corrected, block-only count
        (4) so a future change cannot silently reintroduce port chaining without
        this test catching it.
        """
        port_ids = {b.egress_port_id for b in live_plan.broadcasts}
        port_ids |= {arm.port_id for b in live_plan.broadcasts for c in b.channels for arm in c.arms}

        for a, b in live_plan.band_links:
            assert a not in port_ids and b not in port_ids, (
                f"band link ({a}, {b}) chains a port id -- port-to-port chaining is removed "
                "by the ADR-036 D1 band-ports-not-chained revision"
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
# port-id assertions in the same tests staying byte-identical once D8 landed IS
# the D8 hard invariant this suite pins.
# ============================================================================


class TestD8ArmLabelSubstitutionLiveCorpus:
    """
    Live-corpus proof of items 2, 3, and 6 using the real "identity & authz"
    broadcast -- the corpus's own worked example of a multi-root broadcast whose
    arms land at PEP-wrapped targets (quoted directly from ADR-036 D8's own
    prose: "6 derived arm-label suffixes").

    Port ids captured below were read directly off `build_decoupled_plan()`'s
    output against the real corpus before this suite was written (not guessed).
    `target_short_name()` always lowercases and space-joins (§E), so every arm
    label already exercises item 3's lowercase-surround case (item 1's Title
    Case case is exercised at the node-title site instead, since it is
    title-derived, not id-derived).
    """

    @pytest.fixture(scope="class")
    @classmethod
    def live_corpus(cls, repo_root: Path):
        components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml")
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
                        ("componentIdentityProvider", "componentFederationProxy"),
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
        Item 2 (label half) + item 6: each of the 4 PEP-landing arms in this
        broadcast gets its OWN correctly-prefixed substituted label -- not one
        generic "PEP" losing "agent network"/"application network"/"authorization"/
        "tool network".
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
        stay byte-identical whether the label substitution is implemented or not.
        These exact strings were captured directly from `build_decoupled_plan()`'s
        output against the real corpus before this suite was written -- already
        GREEN before D8 landed, and this test's job is to make sure it stayed
        GREEN once D8 landed (a regression, not a new-behavior, assertion).
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
        `componentModelServing` (bare arm, no PEP phrase at all) and
        `componentFederationProxy` (suffixed, but no PEP phrase either) -- neither
        should ever change, proving the substitution is scoped to labels that
        actually contain the phrase, not applied blanket across every arm in a
        broadcast that happens to have SOME PEP-landing siblings.
        """
        arms = self._arms_by_target(live_plan)
        assert arms["componentModelServing"].label == "identity & authz"
        assert arms["componentFederationProxy"].label == "identity & authz → federation proxy"


class TestD8PdpArmLabelNeverAbbreviated:
    """
    Item 4, arm-label form: 'policy decision point' -> 'PDP' was evaluated
    alongside PEP and explicitly held out of the D8 set (ADR-036 D8: "its single
    occurrence already fits the wrap target, so it has no measured justification").
    This is the regression guard proving the closed, PEP-only set doesn't
    accidentally generalize to a broader "Policy * Point" pattern: a PDP-named arm
    target sits in the SAME multi-arm channel as a PEP-named one, so a naive regex
    catching both would be caught red-handed by this fixture, side by side, in one
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

        # PDP: unaffected -- explicitly held out of the D8 set (was already GREEN
        # before D8 landed, stays GREEN now).
        assert pdp_arm.label == "test concern → authorization policy decision point"
        # PEP: substituted per D8 -- proves this fixture would genuinely catch a
        # naive "Policy * Point" pattern that wrongly abbreviated both, since PDP
        # is asserted unchanged in the SAME assertion pass.
        assert pep_arm.label == "test concern → gateway PEP"


"""
Test Summary
============
Total test functions: 66 (across 17 test classes + 3 pytest fixtures used as synthetic
corpora)

Coverage areas:
- Grammar primitives (slug/root_slug/target_short_name/pep_wrap_base): 13 tests, all
  exact-literal per §E, including both ADR-quoted slug() examples.
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
  never chains two ports sharing a root; was RED against `_build_band_links`
  before the fix, now GREEN).
- Live-corpus inventory (plan §C, independently re-verified numbers): 10 tests
  (includes one ADR-036 D1 regression guard pinning `band_links` to exactly the 4
  block entry/exit pairs, zero port-to-port chain links -- was RED, now GREEN).
- ADR-036 D8 (display-layer acronym substitution, arm-label site): 4 tests across 2
  classes. `TestD8ArmLabelSubstitutionLiveCorpus` -- the real "identity & authz"
  broadcast's 4 PEP-landing arms substitute to "PEP", each keeping its own prefix
  (1 test); the port ids computed from those same targets stay byte-identical
  (1 GREEN-today regression pin, the D8 hard invariant); the broadcast's 2 non-PEP
  arms are unaffected (1 GREEN-today scope guard). `TestD8PdpArmLabelNeverAbbreviated`
  -- a synthetic PDP+PEP mixed channel, PDP unchanged/PEP substituted in the same
  assertion pass (1 test). Node-title-site D8 coverage
  (`_decoupled_member_lines`/`_decoupled_pep_wrap_lines`) lives in
  test_decouple_emitter.py instead -- this file covers only `decouple.py`'s
  `_build_arms`/`arm_label` site plus the port-id invariant.

Notes for the code-reviewer (task 1.3):
- No landing-selection test exists anywhere in this file (R1/R2/R4 checked).
- No `forceSplit`/override-key vocabulary appears anywhere (R3/R7/R11 checked).
- Aspect threshold used throughout is 10 (D4/R6), never 5.
- Two judgment calls flagged inline for explicit reviewer sign-off:
  1. The G-C3 synthesized fallback label uses the FULL category id for srcRoot/tgtRoot
     (`componentsInfrastructure→componentsModel flow`), not root_slug() -- see comment
     in test_uncovered_edge_gets_synthesized_fallback_label_and_warning.
  2. PEP wrap id/in-id/out-id base abbreviation ("PolicyEnforcementPoint" -> "Pep") is
     derived from the single literal example in plan §E and generalized across all PEP
     ids -- see TestPepWrapBaseGrammar.
"""
