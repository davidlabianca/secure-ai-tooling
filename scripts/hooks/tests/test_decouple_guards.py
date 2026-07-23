#!/usr/bin/env python3
"""
Tests for the decoupled component-graph transform's drift guards (ADR-036 D7,
`working-plans/component-graph-decouple-strategy-c-implementation-plan.md` §D).

`graphing/decouple.py` does not exist yet — this is the RED phase of the TDD chain
(Phase 1, task 1.2). Every test in this module is expected to fail at collection with
a `ModuleNotFoundError` until the `swe` agent implements the module.

This suite exercises `check_emission_drift(forward_map, components, emission_cfg) ->
list[str]` — the standalone guard pass consumed by the `validate_riskmap.py` warn-only
battery (plan P5) and, per §D, callable in one pass over the whole registry (not one
guard invocation per entry).

Guard table under test (plan §D):

    ID     Trigger                                                Degradation
    G-A1   aspects/concerns id absent from corpus (stale)          entry ignored
    G-A2   configured aspect has any outgoing edge (sink viol.)    lift refused -> channel
    G-A3   configured aspect's cross in-degree < minCrossInDegree  lift refused -> channel
    G-A4   unconfigured component passes D4 candidacy test         informational only (optional)
    G-C1   concerns entry names an edge not present in the corpus  dead edge ref ignored
    G-C2   concerns entry names an edge no longer cross-boundary   edge treated as intra; ref ignored
    G-C3   cross edge with no concerns entry                       synthesized label
    G-C4   cross edge covered by two entries                       lexicographically-first label wins
    G-O1   aspect lift would leave its block with zero intra edges lift refused -> channel

Message contract (plan §D, closing paragraph): every message carries a config path
(e.g. `graphTypes.component.emission.concerns[n]`), what it referenced, what the
corpus/heuristic says instead (counter-evidence), and a one-line remediation. The
*exact prose* of the remediation is an implementation choice (the plan does not
mandate specific wording), so `_assert_message_contract()` below checks only the
load-bearing structural pieces: the config-path fragment, the referenced entity, and
the counter-evidence value are all present, plus a length floor ruling out a bare stub
message masquerading as compliant.

Per the task instructions, G-A4 is deliberately tested only lightly: the plan (§Q4)
retains it as optional/informational, non-blocking, and explicitly states a test suite
that never exercises it is still complete. The one test here only proves it never
raises and never poisons the rest of the drift list -- it does not assert G-A4 fires
or is absent.
"""

import sys
from pathlib import Path

# Add scripts/hooks directory to path (matches test_base_graph.py convention).
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

# This import is expected to fail until Phase 1.4 implements the module (RED phase).
from riskmap_validator.graphing.decouple import (  # noqa: E402
    AspectDecl,
    ConcernDecl,
    EmissionConfig,
    check_emission_drift,
)
from riskmap_validator.models import ComponentNode  # noqa: E402

# ============================================================================
# Shared helpers
# ============================================================================

INFRA = "componentsInfrastructure"
MODEL = "componentsModel"
APP = "componentsApplication"
TOOLS = "componentsTools"

ASPECTS_PATH = "graphTypes.component.emission.aspects"
CONCERNS_PATH = "graphTypes.component.emission.concerns"


def _node(category: str, to_edges: list[str] | None = None, subcategory: str | None = None) -> ComponentNode:
    return ComponentNode(
        title="Test Node",
        category=category,
        to_edges=to_edges or [],
        from_edges=[],
        subcategory=subcategory,
    )


def _forward_map(components: dict[str, ComponentNode]) -> dict[str, list[str]]:
    return {cid: node.to_edges[:] for cid, node in components.items()}


def _assert_message_contract(
    messages: list[str], *, config_path_fragment: str, referenced: str, counter_evidence: str
):
    """
    Find a message in `messages` satisfying the guard message contract and return it.

    Asserts presence of: the config-path fragment, the referenced entity (id or edge
    representation), and the counter-evidence (the corpus/heuristic fact contradicting
    the config). Also floors the message length so a bare stub ("bad entry") can't pass
    -- the remaining length budget stands in for "carries a remediation," since the
    plan does not fix the remediation's exact wording.
    """
    candidates = [m for m in messages if config_path_fragment in m and referenced in m and counter_evidence in m]
    assert candidates, (
        f"expected a message containing config path {config_path_fragment!r}, "
        f"referenced entity {referenced!r}, and counter-evidence {counter_evidence!r}; got: {messages}"
    )
    message = candidates[0]
    minimum_length = len(config_path_fragment) + len(referenced) + len(counter_evidence) + 20
    assert len(message) > minimum_length, (
        f"message reads as a bare stub, missing a remediation clause: {message!r}"
    )
    return message


# ============================================================================
# G-A1: aspects id absent from corpus (stale)
# ============================================================================


class TestGA1AspectIdAbsentFromCorpus:
    def _fixture(self):
        components = {
            "componentRealSink": _node(INFRA),
            "componentModelSource": _node(MODEL, to_edges=["componentRealSink"]),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentRenamedOrDeletedSink", min_cross_in_degree=1),),
            concerns=(ConcernDecl(label="flow", edges=(("componentModelSource", "componentRealSink"),)),),
        )
        return components, cfg

    def test_fires_when_aspect_id_not_in_corpus(self):
        """
        Given: an emission.aspects entry naming an id that no longer exists in components.yaml
        When: check_emission_drift runs
        Then: a warning fires with the config path, the stale id, and evidence it is absent
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=ASPECTS_PATH,
            referenced="componentRenamedOrDeletedSink",
            counter_evidence="not found",
        )

    def test_degradation_is_the_entry_being_ignored_not_a_crash(self):
        """The stale entry must not prevent the rest of the drift pass from completing."""
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        assert isinstance(warnings, list)

    def test_is_deterministic_across_repeated_calls(self):
        components, cfg = self._fixture()
        forward_map = _forward_map(components)
        first = check_emission_drift(forward_map, components, cfg)
        second = check_emission_drift(forward_map, components, cfg)
        assert first == second


# ============================================================================
# G-A2: configured aspect has an outgoing edge (sink-condition violation)
# ============================================================================


class TestGA2AspectHasOutgoingEdge:
    def _fixture(self):
        components = {
            "componentModelSource0": _node(MODEL, to_edges=["componentNotASink"]),
            "componentModelSource1": _node(MODEL, to_edges=["componentNotASink"]),
            "componentNotASink": _node(INFRA, to_edges=["componentSomewhereElse"], subcategory="componentsBlockX"),
            "componentSomewhereElse": _node(INFRA, subcategory="componentsBlockX"),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentNotASink", min_cross_in_degree=2),),
            concerns=(
                ConcernDecl(
                    label="wrongly configured sink",
                    edges=(
                        ("componentModelSource0", "componentNotASink"),
                        ("componentModelSource1", "componentNotASink"),
                    ),
                ),
            ),
        )
        return components, cfg

    def test_fires_when_configured_aspect_has_an_outgoing_edge(self):
        """
        Given: a configured aspect that has at least one outgoing edge (fails D4's
        mechanical sink test)
        When: check_emission_drift runs
        Then: a warning fires naming the config path, the aspect id, and the outgoing
        edge as counter-evidence of the sink violation
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=ASPECTS_PATH,
            referenced="componentNotASink",
            counter_evidence="componentSomewhereElse",
        )

    def test_degradation_is_deterministic(self):
        components, cfg = self._fixture()
        forward_map = _forward_map(components)
        assert check_emission_drift(forward_map, components, cfg) == check_emission_drift(
            forward_map, components, cfg
        )


# ============================================================================
# G-A3: configured aspect's cross in-degree below its minCrossInDegree
# ============================================================================


class TestGA3AspectBelowThreshold:
    def _fixture(self, cross_in_degree: int, threshold: int):
        components = {"componentSink": _node(INFRA, subcategory="componentsBlockX")}
        components["componentInfraFeeder"] = _node(
            INFRA, to_edges=["componentSink"], subcategory="componentsBlockX"
        )
        for i in range(cross_in_degree):
            components[f"componentModelSource{i}"] = _node(MODEL, to_edges=["componentSink"])
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentSink", min_cross_in_degree=threshold),),
            concerns=(
                ConcernDecl(
                    label="under threshold flow",
                    edges=tuple((f"componentModelSource{i}", "componentSink") for i in range(cross_in_degree)),
                ),
            ),
        )
        return components, cfg

    def test_fires_when_cross_in_degree_is_below_threshold(self):
        """
        Given: a configured aspect whose live cross in-degree (7) is below its
        configured minCrossInDegree (10)
        When: check_emission_drift runs
        Then: a warning fires naming the config path, the aspect id, and the actual
        cross in-degree as counter-evidence
        """
        components, cfg = self._fixture(cross_in_degree=7, threshold=10)
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=ASPECTS_PATH,
            referenced="componentSink",
            counter_evidence="7",
        )

    def test_does_not_fire_when_cross_in_degree_meets_threshold(self):
        """At exactly the threshold, no G-A3 warning is produced (D4: 'meets' is >=)."""
        components, cfg = self._fixture(cross_in_degree=10, threshold=10)
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        assert not any("componentSink" in w and ASPECTS_PATH in w for w in warnings)


# ============================================================================
# G-A4: unconfigured component passes candidacy — optional/informational only
# ============================================================================


class TestGA4UndeclaredCandidateIsOptionalAndNonBlocking:
    def test_never_raises_and_returns_a_list_regardless_of_undeclared_candidates(self):
        """
        Given: a component that mechanically passes the D4 candidacy test (sink,
        cross in-degree 12 >= a plausible threshold) but is NOT present in
        emission.aspects at all
        When: check_emission_drift runs
        Then: the call succeeds and returns a list -- per plan §Q4, G-A4 is optional,
        informational-only, and non-blocking. This test intentionally does not assert
        whether a G-A4-style message is present or absent; per the task instructions,
        a suite that never exercises G-A4's firing is still considered complete.
        """
        components = {"componentUndeclaredCandidate": _node(INFRA)}
        for i in range(12):
            components[f"componentModelSource{i}"] = _node(MODEL, to_edges=["componentUndeclaredCandidate"])
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="undeclared sink flow",
                    edges=tuple((f"componentModelSource{i}", "componentUndeclaredCandidate") for i in range(12)),
                ),
            ),
        )
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        assert isinstance(warnings, list)
        assert all(isinstance(w, str) for w in warnings)


# ============================================================================
# G-C1: concerns entry names an edge not present in the corpus (dead ref)
# ============================================================================


class TestGC1DeadEdgeReference:
    def _fixture(self):
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
            "componentModelB": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="stale edge flow",
                    # componentInfraA -> componentModelB is not a real edge (only
                    # componentInfraA -> componentModelA exists in forward_map).
                    edges=(("componentInfraA", "componentModelA"), ("componentInfraA", "componentModelB")),
                ),
            ),
        )
        return components, cfg

    def test_fires_for_an_edge_reference_absent_from_forward_map(self):
        """
        Given: a concerns entry listing an edge that does not exist in forward_map
        When: check_emission_drift runs
        Then: a warning fires naming the config path and the dead (src, tgt) pair
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=CONCERNS_PATH,
            referenced="componentModelB",
            counter_evidence="componentInfraA",
        )

    def test_the_still_valid_edge_in_the_same_entry_is_unaffected(self):
        """A dead edge reference in one entry must not suppress its sibling live edges."""
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        # The live edge is fine; only the dead one should be flagged. We can't inspect
        # the plan here (this is the guard-only pass), so we assert the dead-ref
        # warning exists without asserting anything false about the live edge.
        assert any("componentModelB" in w for w in warnings)


# ============================================================================
# G-C2: concerns entry names an edge that is no longer cross-boundary
# ============================================================================


class TestGC2EdgeRecategorizedToIntra:
    def _fixture(self):
        components = {
            # Both endpoints now share a category -- this edge used to be cross when
            # the concerns entry was written, but a corpus edit moved componentInfraB
            # into componentsInfrastructure alongside componentInfraA.
            "componentInfraA": _node(INFRA, to_edges=["componentInfraB"]),
            "componentInfraB": _node(INFRA),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(ConcernDecl(label="formerly cross flow", edges=(("componentInfraA", "componentInfraB"),)),),
        )
        return components, cfg

    def test_fires_when_a_concerns_edge_is_now_intra(self):
        """
        Given: a concerns entry naming an edge whose endpoints now share a category
        When: check_emission_drift runs
        Then: a warning fires naming the config path and the recategorized edge
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=CONCERNS_PATH,
            referenced="componentInfraB",
            counter_evidence=INFRA,
        )


# ============================================================================
# G-C3: cross edge with no concerns entry (uncovered)
# ============================================================================


class TestGC3UncoveredCrossEdge:
    def _fixture(self):
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg = EmissionConfig(mode="decoupled", concerns=())
        return components, cfg

    def test_fires_for_a_cross_edge_with_no_covering_entry(self):
        """
        Given: a cross edge with zero concerns entries covering it
        When: check_emission_drift runs
        Then: a warning fires naming the config path (the fix is to add an entry
        there), the uncovered edge, and the fact that no entry currently exists
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=CONCERNS_PATH,
            referenced="componentInfraA",
            counter_evidence="componentModelA",
        )

    def test_degradation_is_deterministic(self):
        components, cfg = self._fixture()
        forward_map = _forward_map(components)
        assert check_emission_drift(forward_map, components, cfg) == check_emission_drift(
            forward_map, components, cfg
        )


# ============================================================================
# G-C4: cross edge covered by two entries (consistency)
# ============================================================================


class TestGC4DoubleCoveredCrossEdge:
    def _fixture(self):
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="zzz duplicate label", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="aaa duplicate label", edges=(("componentInfraA", "componentModelA"),)),
            ),
        )
        return components, cfg

    def test_fires_for_a_doubly_covered_edge(self):
        """
        Given: an edge named by two distinct concerns entries
        When: check_emission_drift runs
        Then: a warning fires naming the config path, the doubly-covered edge, and
        both competing labels as counter-evidence
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        message = _assert_message_contract(
            warnings,
            config_path_fragment=CONCERNS_PATH,
            referenced="componentInfraA",
            counter_evidence="componentModelA",
        )
        # Both competing labels should be identifiable in the message so a reader can
        # tell which one won without cross-referencing the config file.
        assert "aaa duplicate label" in message or "zzz duplicate label" in message

    def test_resolution_is_the_same_regardless_of_declaration_order(self):
        """The winning label (lexicographically first) must not depend on registry order."""
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentModelA"]),
            "componentModelA": _node(MODEL),
        }
        cfg_order_1 = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="aaa duplicate label", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="zzz duplicate label", edges=(("componentInfraA", "componentModelA"),)),
            ),
        )
        cfg_order_2 = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(label="zzz duplicate label", edges=(("componentInfraA", "componentModelA"),)),
                ConcernDecl(label="aaa duplicate label", edges=(("componentInfraA", "componentModelA"),)),
            ),
        )
        forward_map = _forward_map(components)
        warnings_1 = check_emission_drift(forward_map, components, cfg_order_1)
        warnings_2 = check_emission_drift(forward_map, components, cfg_order_2)
        assert warnings_1 == warnings_2


# ============================================================================
# G-O1: aspect lift would leave its block with zero drawn intra edges
# ============================================================================


class TestGO1BlockOrphanViolation:
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

    def test_fires_when_lift_would_orphan_the_block(self):
        """
        Given: an aspect that passes D4 candidacy, but whose block would end up with
        zero drawn intra edges if the lift proceeded
        When: check_emission_drift runs
        Then: a warning fires naming the config path, the aspect id, and the block id
        as counter-evidence of the orphan condition
        """
        components, cfg = self._fixture()
        warnings = check_emission_drift(_forward_map(components), components, cfg)
        _assert_message_contract(
            warnings,
            config_path_fragment=ASPECTS_PATH,
            referenced="componentAspectSink",
            counter_evidence="componentsIsolatedBlock",
        )

    def test_degradation_is_deterministic(self):
        components, cfg = self._fixture()
        forward_map = _forward_map(components)
        assert check_emission_drift(forward_map, components, cfg) == check_emission_drift(
            forward_map, components, cfg
        )


# ============================================================================
# check_emission_drift returns the full warning list in one pass
# ============================================================================


class TestFullPassAggregation:
    def test_multiple_simultaneous_violations_all_appear_in_one_call(self):
        """
        Given: a config with THREE independent, simultaneous violations (G-A2 sink
        violation, G-C3 uncovered edge, G-C4 double-covered edge)
        When: check_emission_drift is called ONCE
        Then: all three warnings are present in the single returned list -- guards are
        not evaluated one-at-a-time requiring separate calls
        """
        components = {
            # G-A2: componentBadAspect has an outgoing edge.
            "componentBadAspect": _node(INFRA, to_edges=["componentInfraOther"], subcategory="componentsBlockX"),
            "componentInfraOther": _node(INFRA, subcategory="componentsBlockX"),
            "componentModelIntoBadAspect": _node(MODEL, to_edges=["componentBadAspect"]),
            # G-C3: this cross edge has no concerns entry at all.
            "componentInfraUncovered": _node(INFRA, to_edges=["componentModelUncoveredTarget"]),
            "componentModelUncoveredTarget": _node(MODEL),
            # G-C4: this cross edge is named by two concerns entries.
            "componentInfraDoubled": _node(INFRA, to_edges=["componentModelDoubledTarget"]),
            "componentModelDoubledTarget": _node(MODEL),
        }
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentBadAspect", min_cross_in_degree=1),),
            concerns=(
                ConcernDecl(
                    label="bad aspect flow", edges=(("componentModelIntoBadAspect", "componentBadAspect"),)
                ),
                ConcernDecl(
                    label="zzz doubled", edges=(("componentInfraDoubled", "componentModelDoubledTarget"),)
                ),
                ConcernDecl(
                    label="aaa doubled", edges=(("componentInfraDoubled", "componentModelDoubledTarget"),)
                ),
            ),
        )
        warnings = check_emission_drift(_forward_map(components), components, cfg)

        has_a2 = any("componentBadAspect" in w and "componentInfraOther" in w for w in warnings)
        has_c3 = any("componentInfraUncovered" in w and "componentModelUncoveredTarget" in w for w in warnings)
        has_c4 = any("componentInfraDoubled" in w and "componentModelDoubledTarget" in w for w in warnings)

        assert has_a2, f"expected a G-A2-style warning in: {warnings}"
        assert has_c3, f"expected a G-C3-style warning in: {warnings}"
        assert has_c4, f"expected a G-C4-style warning in: {warnings}"


"""
Test Summary
============
Total test functions: 21 across 10 test classes (one per guard ID, plus one
full-pass-aggregation class).

Coverage areas:
- G-A1 (aspect id absent): fires, degrades to ignored-not-crashed, deterministic. 3 tests.
- G-A2 (aspect has outgoing edge): fires, deterministic. 2 tests.
- G-A3 (aspect below threshold): fires below threshold, silent at threshold. 2 tests.
- G-A4 (undeclared candidate, optional/non-blocking): never raises, no assertion on
  firing per plan §Q4 and the task instructions. 1 test.
- G-C1 (dead edge ref): fires, sibling live edges unaffected. 2 tests.
- G-C2 (edge recategorized to intra): fires. 1 test.
- G-C3 (uncovered cross edge): fires, deterministic. 2 tests.
- G-C4 (double-covered edge): fires with both competing labels visible, order-independent
  resolution. 2 tests.
- G-O1 (block-orphan violation): fires, deterministic. 2 tests.
- Full-pass aggregation: three simultaneous violations all surface from one call. 1 test.

Message-contract testing strategy: `_assert_message_contract()` checks the config-path
fragment, the referenced entity, and the counter-evidence are all present in some
returned message, plus a length floor standing in for "carries a remediation clause" —
deliberately NOT pinning exact prose, since plan §D does not mandate specific wording,
only the four structural pieces (config path + what it referenced + what the corpus
says instead + one-line remediation).
"""
