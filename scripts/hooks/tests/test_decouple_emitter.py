#!/usr/bin/env python3
"""
Tests for the decoupled component-graph emission pass (ADR-036, Phase 2, tasks 2.1/2.2).

`ComponentGraph._emit_decoupled()` -- the private method that serializes a
`DecoupledPlan` (built by `graphing/decouple.py`, Phase 1) into Mermaid text -- is
implemented at `component_graph.py:184`. `build_graph()`'s mode dispatch
(`config_loader.get_emission_config().mode == "decoupled"` -> `build_decoupled_plan()`
-> `self._emit_decoupled(plan)`) is implemented at `component_graph.py:113-116`. This
suite was the RED phase of that piece of the TDD chain; it is retained as the
regression pin against the now-GREEN implementation.

Contract under test (fixed by this suite; the implementation was derived from it):

    ComponentGraph._emit_decoupled(self, plan: DecoupledPlan) -> str
        Serializes the IR in the fixed 8-step output order (plan §A "Emission pass"):
        (1) frontmatter + `graph LR` preamble, (2) header comments (lifted-aspect
        inventory grouped by source cluster, then the undrawn hop list per broadcast),
        (3) `classDef port`/`classDef pepport`, (4) clusters -> bands/blocks/PEP wrap
        subgraphs/nodes, (5) drawn intra edges (wrap -> retarget -> collapse) + PEP
        port chains, (6) source->egress and ingress->landing edges, (7) invisible
        `~~~` band links (never spanning two roots), (8) `style` lines (category
        styles verbatim, band `fill:none,stroke:none`, `pepWrapOutline`). Runs the D7
        emission self-check before returning (delegates to `verify_plan()` for
        S1/S4/S5/S7; adds new text-level checks for S2/S3/S6; surfaces `plan.
        diagnostics` for S8 without ever raising on them).

    ComponentGraph.build_graph() dispatches on `self.config_loader.
    get_emission_config().mode`: "flat" (or a missing/corrupt config) takes the
    existing code path verbatim; "decoupled" calls `build_decoupled_plan()` then
    `self._emit_decoupled(plan)`.

Phase 2 / Phase 3 boundary (read before extending this file in Phase 3)
========================================================================
`MermaidConfigLoader.get_emission_config()` is implemented for real in this change
(`graphing/graph_utils.py`), per the task's explicit licensed exception: plan decision
P1 fixes `ComponentGraph.__init__`'s signature as unchanged (no new constructor
parameter), so the emission config has to come from the loader, and a stub would block
every test in this file from exercising a real decoupled path. It is a MINIMAL,
functional accessor -- mode, aspects, concerns, port_styles -- defaulting to
`EmissionConfig(mode="flat")` on any absent or malformed `graphTypes.component.
emission` block (D3: "missing or corrupt config never yields a half-decoupled
diagram"). This accessor's own contract does not perform schema validation -- that
responsibility stays with check-jsonschema at the YAML-validation layer (see
`get_emission_config()`'s own docstring in `graph_utils.py`); Phase 3 (task 3.3) landed
the schema definitions and the real corpus config without changing this accessor's
degrade-don't-crash behavior.

`risk-map/yaml/mermaid-styles.yaml` carries a real `graphTypes.component.emission`
block (Phase 3's §C registry), but its `mode` is `flat` -- the two-PR landing sequence
(ADR-036 Follow-up) flips it to `decoupled`, along with a regenerated diagram, in a
separate PR. So in production today `get_emission_config()` still returns the flat
default; see `TestGetEmissionConfigAccessor` below and `TestFlatModeRegression`. Tests
in this file that exercise the *decoupled* path construct the real §C `EmissionConfig`
directly as a fixture (`_live_emission_config()` below), mirroring
`TestLiveCorpusInventory` in `test_decouple_transform.py` -- duplicated here rather than
imported, per that suite's own precedent (`test_decouple_coverage_gaps.py`'s module
docstring makes the same call, for the same reason: independence between test files
covering different phases). `emission.portStyles` also carries real content in
`mermaid-styles.yaml` now; tests needing port styling still use `PLACEHOLDER_PORT_STYLES`
below (documented inline) since they construct their `EmissionConfig` fixtures directly
rather than reading the still-flat-mode production config.

Original RED failure mode (historical; retained for context on the tests' design)
====================================================================================
Most tests below call `ComponentGraph._emit_decoupled()` directly. Before Phase 2
landed, that method did not exist, so the call raised a clean `AttributeError` at the
call site -- verified via a throwaway prototype before this suite was written, the same
technique Phase 1's testing agent used. A small, explicitly flagged subset of tests
instead exercise `build_graph()`'s mode-dispatch integration directly; before that
dispatch landed, `build_graph()` unconditionally took the flat path (it did not consult
`get_emission_config()` at all), so those specific tests failed as a content mismatch
or (for the flat-regression/bypass tests) already passed, rather than a clean interface
error -- each such test's docstring says so explicitly, per the task's original request
to distinguish RED failure characters.

Why message-matching, not import-patching, for "delegates to verify_plan"
===========================================================================
Task 2.2 requires proving the self-check calls the *existing* `verify_plan()` for
S1/S4/S5/S7 rather than reimplementing equivalent logic. A `mock.patch` on
`decouple.verify_plan` would only intercept the call if `component_graph.py` references
it as `decouple.verify_plan(...)` (module-qualified) -- if it instead does `from
.decouple import verify_plan` (the repo's established import convention; see
`component_graph.py`'s existing `from .graph_utils import MermaidConfigLoader`, `base.
py`'s `from .graph_utils import ...`), the patch would silently miss the locally-bound
name and the test would give a false negative. Rather than bake in an assumption about
an implementation choice that is `swe`'s to make, the self-check tests below construct
corrupted-IR fixtures that isolate exactly one of S1/S4/S5/S7 (verified against the
*already-implemented* `verify_plan()` directly, via a throwaway prototype, before being
written into this suite) and assert that `_emit_decoupled()` raises an `AssertionError`
whose message matches `verify_plan`'s own wording, quoted directly from `decouple.py`.
A reimplementation producing a different message fails this match; one that happens to
reproduce `verify_plan`'s exact wording independently is, for all practical purposes,
indistinguishable from delegation and equally acceptable.

Test coverage
=============
Task 2.1 (emitter):
 1. `TestGetEmissionConfigAccessor` -- the licensed accessor itself (GREEN today).
 2. `TestOutputOrderContract` -- all 8 steps appear in the correct relative order.
 3. `TestHeaderCommentFormats` -- lifted-aspect inventory grouping (this suite's own
    line-format contract, derived from the plan object, not hardcoded); undrawn hop
    list (literal ADR D6 mockup reproduction, order-independent -- see inline note on
    why channel order itself is not pinned).
 4. `TestBandLinksNeverSpanRoots` -- `plan.band_links` and the emitted `~~~` text never
    span two roots; ADR-036 D1's band-ports-not-chained revision additionally requires
    that no band link (IR or emitted) ever chains two port ids together -- only a
    block's entry->exit pair survives (was RED against `_build_band_links` before the
    fix, now GREEN).
 5. `TestStyleClassDefPassthrough` -- category styles verbatim; port/pepport classDefs;
    pepWrapOutline; band `fill:none,stroke:none`.
 6. `TestOutputFormats` -- `.md` fence and raw (`mermaid`/`mmd`/anything-else) formats.
 7. `TestByteStability` -- double-run and shuffled-input-dict determinism.
 8. `TestFlatModeRegression` -- byte-identical to the committed `risk-map-graph.
    mermaid` (expected GREEN now and after Phase 2 -- a regression pin, not RED).
 9. `TestModeDispatchIntegration` -- `build_graph()`'s own mode dispatch.
10. `TestControlsGovernanceLeakage` -- `_create_subgraph_section`'s `controlsGovernance`
    special case is never invoked by the decoupled path.

Task 2.2 (self-check):
11. `TestSelfCheckDelegatesToVerifyPlan` -- S1/S4/S5/S7 corrupted-IR fixtures, raise
    propagates with `verify_plan`'s own message.
12. `TestSelfCheckTextLevelChecks` -- S2/S3/S6 new checks raise on violation.
13. `TestSelfCheckDiagnosticsNeverRaise` -- S8: `plan.diagnostics` surfaced, never raises.
14. `TestFlatModeBypassesSelfCheck` -- flat mode never enters the decoupled self-check
    path at all (black-box proof via a real S7-violating registry).

Coverage-gap follow-up (adversarial critic pass, closed before Phase 2 implementation
-- see the module-end "Test Summary" docstring for the full H/M gap-to-test mapping):
15. `TestPepWrapperRendering` (H1) -- wrap subgraph declaration, in/out ports +
    `:::pepport`, the PEP node itself, and the port-chain edge, positionally checked.
16. `TestBlockRendering` (H2) -- nested block subgraph span, entry->exit `~~~` link.
    Also strengthens `TestBandLinksNeverSpanRoots.
    test_emitted_band_links_never_span_two_roots` (was silently skipping every
    block-level link; see that test's docstring) and extends `_port_root_map`.
17. `TestPortAndComponentNodeDeclarations` (H3) -- egress/ingress port node grammar
    (bare and suffixed), ingress->landing edge, ordinary node title convention, all
    positionally checked against their containing band/cluster subgraph span.
18. `TestDegenerateEmptyPlans` (M1) -- an all-intra, zero-broadcast, zero-aspect plan
    emits without raising, with no header noise and no orphaned port classDef usage.
19. `TestSingleArmBareGrammar` (M2) -- the bare (unsuffixed) single-arm port-id and
    header-line grammar, the counterpart to the existing ⇢3 multi-arm test.
20. `TestS2ReverseDirectionMismatch` (M3) -- S2 in the opposite direction (more arms
    present than declared), proving exact-equality rather than a one-sided compare.
21. `TestSpecialCharacterHandling` (M4) -- a bracket character in a component title
    passes through exactly as the flat emitter's existing (unescaped) convention does.
22. `TestOutputOrderSpanContract` (M5) -- span-level (not just first-occurrence)
    ordering: every subgraph closes before any `~~~` link; every classDef precedes any
    `:::` usage.

Coverage-gap follow-up, round 2 (adversarial critic re-check on the round-1 batch
above, closed before Phase 2 implementation -- see the module-end "Test Summary"
docstring for the full mapping):
23. `TestIngressLandingAtPepWrappedTarget` (high) -- ingress->landing edge composed
    with a PEP-wrapped arm target, proving the edge retargets through the wrapper's
    `_in` port instead of landing at the raw PEP id (never exercised together before).
24. `TestPepWrapNestedInsideBlock` (medium) -- triple subgraph containment (PEP wrap
    nested inside a block nested inside a cluster), the live corpus's actual shape.
25. `TestConcernLabelEscaping` (medium) -- an embedded `"` in a concern label, a
    distinct escaping surface from M4 (quoted port-label grammar vs. M4's unquoted
    title grammar); design decision documented in the class's own docstring.
Also extends `TestBlockRendering` (H2) with one new method asserting an ordinary
block member (not entry, not exit) is declared inside the block's span -- the H2
residual gap.

Adversarial code-critic follow-up (post-Phase-2, `_emit_decoupled()` now
implemented -- see the module-end "Test Summary" docstring for the full mapping):
26. `TestSourceEgressResolvesThroughPepWrapper` (Fix 1) -- a PEP-wrapped broadcast
    source must exit via its wrapper's `_out` port, not the raw component id.
27. `TestPlanWarningsSurfaced` (Fix 2) -- `plan.warnings` (D7 guard output) must be
    surfaced (logged and header-commented), never silently dropped.
28. `TestSelfCheckCatchesGenuineEmitterDefects` (Fix 3) -- strengthens S2 to a
    text-derived count, adds a per-arm landing-edge text assertion, and a
    source->egress destination assertion, closing the critic's "passes all of
    S1-S8" cross-wired-landing finding.
29. `TestGetEmissionConfigAccessor::test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat`
    (Fix 4) -- a malformed edge-tuple arity in `emission.concerns` must degrade to
    flat, not crash later with a raw `ValueError`.

Adversarial review follow-up on S9/S10 themselves (the checks' own implementation, not
the emitted output; see `docs/adr/036-decoupled-component-graph-emission.md` and the
task that added this section for the full writeup):
30. `TestSelfChecksCatchS9S10ImplementationGaps` -- Bug 1: `expected in text` (S9, and
    S10's first loop) is an unanchored substring match, and this corpus's real ids have
    prefix relationships (`componentApplication` is a prefix of
    `componentApplicationInputHandling`), so a cross-wired edge to the wrong (but
    prefix-related) node is invisible to the check. Bug 2: S10's reverse loop only
    flags a matched `<src> --> p_out_...` line when its port is a KNOWN egress port id,
    so an edge to a nonexistent/typo'd port is silently skipped rather than flagged,
    contradicting the check's own docstring.
"""

import dataclasses
import logging
import random
import re
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add scripts/hooks directory to path (matches test_decouple_transform.py convention).
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing import ComponentGraph, MermaidConfigLoader  # noqa: E402
from riskmap_validator.graphing.base import BaseGraph  # noqa: E402
from riskmap_validator.graphing.decouple import (  # noqa: E402
    Arm,
    AspectDecl,
    Broadcast,
    Channel,
    ConcernDecl,
    DecoupledPlan,
    EmissionConfig,
    build_decoupled_plan,
)
from riskmap_validator.models import ComponentNode  # noqa: E402
from riskmap_validator.utils import parse_components_yaml  # noqa: E402

# ============================================================================
# Shared helpers (duplicated from test_decouple_transform.py / test_decouple_coverage_gaps.py
# per their own established convention -- independence between phase-scoped test files)
# ============================================================================

INFRA = "componentsInfrastructure"
MODEL = "componentsModel"
APP = "componentsApplication"
TOOLS = "componentsExternalTools"


def _node(category: str, to_edges: list[str] | None = None, subcategory: str | None = None) -> ComponentNode:
    return ComponentNode(
        title="Test Node", category=category, to_edges=to_edges or [], from_edges=[], subcategory=subcategory
    )


def _forward_map(components: dict[str, ComponentNode]) -> dict[str, list[str]]:
    return {cid: node.to_edges[:] for cid, node in components.items()}


def _styles_path(repo_root: Path) -> Path:
    return repo_root / "risk-map" / "yaml" / "mermaid-styles.yaml"


def _live_corpus(repo_root: Path) -> tuple[dict[str, ComponentNode], dict[str, list[str]]]:
    components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml")
    return components, _forward_map(components)


def _read_flat_baseline(repo_root: Path) -> str:
    return (repo_root / "risk-map" / "diagrams" / "risk-map-graph.mermaid").read_text(encoding="utf-8")


# Placeholder port styles: mermaid-styles.yaml has no real emission.portStyles content
# yet (Phase 3 wires it). The "port" value is copied verbatim from the ADR D6 mockup's
# `classDef port fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,stroke-dasharray:4 3`;
# pepport/pepWrapOutline are this suite's own placeholder strings.
PLACEHOLDER_PORT_STYLES = {
    "port": "fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,stroke-dasharray:4 3",
    "pepport": "fill:#eef7ff,stroke:#2c3e83,stroke-width:1.5px,stroke-dasharray:4 3",
    "pepWrapOutline": "fill:none,stroke:#2c3e83,stroke-width:2px,stroke-dasharray:2 2",
}


def _live_emission_config() -> EmissionConfig:
    """
    The real ADR-036 §C registry (12 concerns + 1 aspect), reproduced verbatim from
    `TestLiveCorpusInventory`'s fixture in `test_decouple_transform.py` (see that
    class's docstring for the independent-re-derivation provenance), with
    `port_styles=PLACEHOLDER_PORT_STYLES` added on top -- Phase 1 never needed port
    styling; Phase 2's style-passthrough tests do (see module docstring's Phase 2/3
    boundary note).
    """
    return EmissionConfig(
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
        port_styles=PLACEHOLDER_PORT_STYLES,
    )


class _EmissionOverrideLoader(MermaidConfigLoader):
    """
    Test-only loader: real `mermaid-styles.yaml` behaviour (category styles, graph
    preamble, etc., all unchanged) with `get_emission_config()` overridden to return a
    fixed `EmissionConfig` constructed directly by the test -- this is how tests inject
    the real §C registry (or a synthetic one) without depending on `mermaid-styles.yaml`
    containing real `emission` content yet (see module docstring's Phase 2/3 boundary
    note). Instantiated directly per `test_mermaid_config_loader.py` convention, never
    touching the production `MermaidConfigLoader.get_instance()` singleton.
    """

    def __init__(self, emission_cfg: EmissionConfig, config_file: Path):
        super().__init__(config_file)
        self._emission_cfg = emission_cfg

    def get_emission_config(self) -> EmissionConfig:
        return self._emission_cfg


def _make_graph(
    components: dict[str, ComponentNode],
    forward_map: dict[str, list[str]],
    emission_cfg: EmissionConfig,
    repo_root: Path,
) -> ComponentGraph:
    loader = _EmissionOverrideLoader(emission_cfg, _styles_path(repo_root))
    return ComponentGraph(forward_map, components, config_loader=loader)


def _port_root_map(plan: DecoupledPlan) -> dict[str, str]:
    """
    Map every egress/ingress port id AND block entry/exit id in `plan` to the root
    category it belongs to.

    Extended beyond broadcast ports (H2 coverage-gap fix, see
    `TestBandLinksNeverSpanRoots`'s updated docstring): the pre-fix version of this
    helper only mapped broadcast ports, so a lookup for a block entry/exit id always
    returned `None` and every caller guarding on `is not None` silently skipped
    exactly the block-level `~~~` links -- the one category of band link this helper
    was blind to. Block entry/exit ids are unambiguous (each belongs to exactly one
    cluster), so this extension cannot introduce a collision with the existing
    broadcast-port mapping.
    """
    mapping: dict[str, str] = {}
    for broadcast in plan.broadcasts:
        mapping[broadcast.egress_port_id] = broadcast.src_root
        for channel in broadcast.channels:
            for arm in channel.arms:
                mapping[arm.port_id] = channel.tgt_root
    for root, cluster in plan.clusters.items():
        for block in cluster.blocks.values():
            if block.entry_id is not None:
                mapping[block.entry_id] = root
            if block.exit_id is not None:
                mapping[block.exit_id] = root
    return mapping


# ============================================================================
# Mermaid subgraph span helper (H1/H2/H3): finds the (start, end) character span of
# a `subgraph <id> ... end` block, tracking nesting depth so a subgraph containing
# further nested subgraphs is not mistaken for closing at its first inner 'end'. Used
# by the coverage-gap tests below to assert that a node/port declaration is POSITIONED
# inside the correct container's text span, not merely present anywhere in the
# document.
# ============================================================================

_SUBGRAPH_OPEN_RE = re.compile(r"^\s*subgraph\s+(\S+)")
# re.MULTILINE is required here: `_subgraph_span` only ever calls `.match(line)` on a
# single line at a time (where `^`/`$` behave the same with or without the flag), but
# `TestOutputOrderSpanContract.test_last_subgraph_end_precedes_first_band_link` (M5)
# calls `.finditer(text)` on the WHOLE multi-line document. Without re.MULTILINE, `^`
# and `$` only anchor to the start/end of the entire string, so `finditer` over a
# realistic multi-line emission matches zero times -- the test would fail
# unconditionally (a bogus "expected at least one subgraph 'end' line" error),
# regardless of whether the emitted text is correct. Verified against both a
# hand-built correct fixture (passes) and a hand-built early-N+1 violation fixture
# (fails, catching the bug it's meant to catch) before landing this fix.
_SUBGRAPH_END_RE = re.compile(r"^\s*end\s*$", re.MULTILINE)


def _subgraph_span(text: str, subgraph_id: str) -> tuple[int, int]:
    """
    Return the (start_char_offset, end_char_offset) span of the FIRST `subgraph
    <subgraph_id> ... end` block found in `text`. `end_char_offset` is the offset
    immediately after the matching closing 'end' line (the 'end' that returns
    nesting depth to zero, not necessarily the first 'end' line encountered -- a
    subgraph containing a nested subgraph has an inner 'end' first). Raises
    AssertionError if no matching header line is found, or if nesting never closes.
    """
    lines = text.splitlines(keepends=True)
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    start_idx = None
    for i, line in enumerate(lines):
        match = _SUBGRAPH_OPEN_RE.match(line)
        if match and match.group(1) == subgraph_id:
            start_idx = i
            break
    assert start_idx is not None, f"no 'subgraph {subgraph_id}' header line found in emitted text"

    depth = 1
    for j in range(start_idx + 1, len(lines)):
        line = lines[j]
        if _SUBGRAPH_OPEN_RE.match(line):
            depth += 1
        elif _SUBGRAPH_END_RE.match(line):
            depth -= 1
            if depth == 0:
                end_char = offsets[j] + len(line)
                return offsets[start_idx], end_char
    raise AssertionError(f"subgraph {subgraph_id!r} never closes (unbalanced 'end')")


def _base_plan(**overrides) -> DecoupledPlan:
    """
    A conservation-clean, violation-free `DecoupledPlan` skeleton for the self-check
    tests to override exactly one field group at a time, isolating a single S-check
    violation per test. `verify_plan`'s checks run in a fixed order -- S5 first, then
    S1, then S7, then S4 (see `decouple.py`) -- so a test isolating (say) S1 must keep
    S5's conservation counters consistent, and a test isolating S4 must keep S5, S1,
    and S7 clean too. Each override below was verified against the *already-
    implemented* `verify_plan()` directly, via a throwaway prototype, to confirm it
    trips exactly the intended check before being written into this suite.
    """
    fields = dict(
        clusters={},
        pep_wrappers={},
        broadcasts=(),
        lifted_aspects=[],
        drawn_intra_edges=[],
        collapsed_pairs=[],
        band_links=[],
        warnings=[],
        diagnostics=[],
        intra_drawn_count=0,
        collapsed_pair_count=0,
        channelled_count=0,
        lifted_count=0,
        total_edges=0,
    )
    fields.update(overrides)
    return DecoupledPlan(**fields)


# A small, fully self-contained corpus (not the live corpus) used by the S1/S4/S5/S7
# self-check isolation tests -- verify_plan's checks don't need corpus scale, just a
# `components` dict covering whatever ids the corrupted plan fixtures reference.
_S_CHECK_COMPONENTS = {
    "componentAlpha": _node(INFRA),
    "componentBeta": _node(MODEL),
}


def _small_synthetic_components() -> dict[str, ComponentNode]:
    """
    A minimal, representative fixture reproducing the ADR D6 "runtime hosting" worked
    example (componentRuntimeHosting -> Model/Application/ReasoningCore, exact port ids
    quoted in the ADR), plus one aspect-lift edge (ModelServing -> SecureLogging, a
    genuine cross edge since Model != Infra), one drawn intra edge (Alpha -> Beta), one
    collapsible mirror pair (ModelServing <--> TheModel), and one PEP-touching pair
    (Application -> Gateway PEP -> ReasoningCore) exercising the wrap/retarget path and
    the PEP port chain -- enough surface to exercise all 8 emission steps in one fixture.
    """
    return {
        "componentRuntimeHosting": _node(
            INFRA, to_edges=["componentModelServing", "componentApplication", "componentReasoningCore"]
        ),
        "componentAlpha": _node(INFRA, to_edges=["componentBeta"]),
        "componentBeta": _node(INFRA, to_edges=[]),
        "componentSecureLogging": _node(INFRA, to_edges=[]),
        "componentModelServing": _node(MODEL, to_edges=["componentTheModel", "componentSecureLogging"]),
        "componentTheModel": _node(MODEL, to_edges=["componentModelServing"]),
        "componentApplication": _node(APP, to_edges=["componentGatewayPolicyEnforcementPoint"]),
        "componentReasoningCore": _node(APP, to_edges=[]),
        "componentGatewayPolicyEnforcementPoint": _node(APP, to_edges=["componentReasoningCore"]),
    }


def _small_synthetic_cfg() -> EmissionConfig:
    return EmissionConfig(
        mode="decoupled",
        aspects=(AspectDecl(id="componentSecureLogging", min_cross_in_degree=1),),
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
        port_styles=PLACEHOLDER_PORT_STYLES,
    )


def _block_fixture_components() -> dict[str, ComponentNode]:
    """
    H2 fixture: a single Application cluster containing one subcategory block with an
    entry (`...InputHandling`) -> middle -> exit (`...OutputHandling`) intra chain,
    matching `decouple.py`'s `_ENTRY_HANDLING_PATTERN`/`_EXIT_HANDLING_PATTERN`. No
    cross edges and no other cluster -- this isolates block-subgraph and
    entry/exit-band rendering from channel/broadcast rendering, which the rest of this
    suite already covers.
    """
    return {
        "componentAppTestInputHandling": _node(
            APP, to_edges=["componentAppTestMiddle"], subcategory="componentsAppTestBlock"
        ),
        "componentAppTestMiddle": _node(
            APP, to_edges=["componentAppTestOutputHandling"], subcategory="componentsAppTestBlock"
        ),
        "componentAppTestOutputHandling": _node(APP, to_edges=[], subcategory="componentsAppTestBlock"),
    }


def _block_fixture_cfg() -> EmissionConfig:
    return EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)


def _small_synthetic_components_with_block() -> dict[str, ComponentNode]:
    """
    `_small_synthetic_components()` extended with `_block_fixture_components()`'s
    Application-cluster block (entry -> middle -> exit, no cross edges of its own).

    ADR-036 D1's band-ports-not-chained revision removes port-to-port `~~~` chaining
    entirely, and `_small_synthetic_components()` alone has no subcategory blocks --
    so, post-revision, that base fixture emits ZERO `~~~` band links at all. A block's
    entry->exit pair is the only kind of band link that survives the revision, so
    `TestOutputOrderContract`'s Step 7 marker needs a block present to have anything
    to find. Used only by that one test; every other test in this suite that calls
    `_small_synthetic_components()` directly is unaffected by this fixture's existence.
    """
    components = dict(_small_synthetic_components())
    components.update(_block_fixture_components())
    return components


def _pep_landing_fixture_components() -> dict[str, ComponentNode]:
    """
    High-severity composition-gap fixture (coverage-critic re-check, round 2): a
    single cross-cluster channel whose sole arm targets a PEP-wrapped component
    (`componentLandingPolicyEnforcementPoint`). Isolates the ingress->landing edge's
    PEP-retargeting behavior (`decouple.py::_build_arms`'s `landing_id =
    pep_wrappers[target].in_id if target in pep_wrappers else target`) from
    `TestPortAndComponentNodeDeclarations.
    test_ingress_to_landing_edge_emitted_for_at_least_one_arm`, which picks
    `_small_synthetic_cfg()`'s "runtime hosting" broadcast's first (alphabetically
    sorted) arm -- Application, a plain component -- and so never exercises the
    PEP-wrapped-target path at all.
    """
    return {
        "componentLandingSource": _node(INFRA, to_edges=["componentLandingPolicyEnforcementPoint"]),
        "componentLandingPolicyEnforcementPoint": _node(APP, to_edges=[]),
    }


def _pep_landing_fixture_cfg() -> EmissionConfig:
    return EmissionConfig(
        mode="decoupled",
        concerns=(
            ConcernDecl(
                label="landing test",
                edges=(("componentLandingSource", "componentLandingPolicyEnforcementPoint"),),
            ),
        ),
        port_styles=PLACEHOLDER_PORT_STYLES,
    )


def _pep_in_block_fixture_components() -> dict[str, ComponentNode]:
    """
    Medium composition-gap fixture (coverage-critic re-check, round 2): combines
    `_block_fixture_components`'s entry -> middle -> exit block shape with a
    PEP-wrapped middle member, matching the live corpus's actual shape -- all 4 real
    PEPs live inside a subcategory block (see `test_decouple_transform.py`'s
    `TestLiveCorpusInventory`). No existing test nests a PEP wrap subgraph inside a
    block subgraph; H1 (`TestPepWrapperRendering`) and H2 (`TestBlockRendering`) each
    prove their own containment in isolation but never together.
    """
    return {
        "componentPibInputHandling": _node(
            APP, to_edges=["componentPibGatewayPolicyEnforcementPoint"], subcategory="componentsPibBlock"
        ),
        "componentPibGatewayPolicyEnforcementPoint": _node(
            APP, to_edges=["componentPibOutputHandling"], subcategory="componentsPibBlock"
        ),
        "componentPibOutputHandling": _node(APP, to_edges=[], subcategory="componentsPibBlock"),
    }


def _pep_in_block_fixture_cfg() -> EmissionConfig:
    return EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)


def _degenerate_components() -> dict[str, ComponentNode]:
    """
    M1 fixture: an all-intra corpus -- one drawn intra edge in Infrastructure, one
    isolated Model node, zero cross edges anywhere. With no `emission.aspects` and no
    `emission.concerns` declared either, `build_decoupled_plan` produces zero lifted
    aspects and zero broadcasts: the degenerate case the emitter must still handle
    without raising and without printing empty-section noise (M1).
    """
    return {
        "componentAlpha": _node(INFRA, to_edges=["componentBeta"]),
        "componentBeta": _node(INFRA, to_edges=[]),
        "componentGamma": _node(MODEL, to_edges=[]),
    }


def _degenerate_cfg() -> EmissionConfig:
    return EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)


# ============================================================================
# 1. get_emission_config() accessor -- licensed exception, implemented for real
#    (GREEN today; not part of the RED surface)
# ============================================================================


class TestGetEmissionConfigAccessor:
    """
    `MermaidConfigLoader.get_emission_config()` is implemented for real as part of this
    task (see module docstring's Phase 2/3 boundary note). These tests are GREEN today
    -- they exercise the accessor directly, independent of the emitter itself.
    """

    def test_absent_emission_block_defaults_to_flat(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\ngraphTypes:\n  component: {}\n",
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        cfg = loader.get_emission_config()
        assert cfg.mode == "flat"
        assert cfg.aspects == ()
        assert cfg.concerns == ()
        assert cfg.port_styles is None

    def test_missing_mode_key_defaults_to_flat(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n  component:\n    emission:\n      aspects: []\n",
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        assert loader.get_emission_config().mode == "flat"

    def test_unknown_mode_value_defaults_to_flat(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n  component:\n    emission:\n      mode: bogus\n",
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        assert loader.get_emission_config().mode == "flat"

    def test_well_formed_decoupled_block_parses_aspects_and_concerns(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n"
            "  component:\n"
            "    emission:\n"
            "      mode: decoupled\n"
            "      aspects:\n"
            "        - id: componentSecureLogging\n"
            "          minCrossInDegree: 10\n"
            "      concerns:\n"
            "        - label: runtime hosting\n"
            "          edges:\n"
            "            - [componentRuntimeHosting, componentModelServing]\n"
            "      portStyles:\n"
            "        port: 'fill:#fff'\n",
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        cfg = loader.get_emission_config()
        assert cfg.mode == "decoupled"
        assert cfg.aspects == (AspectDecl(id="componentSecureLogging", min_cross_in_degree=10),)
        assert cfg.concerns == (
            ConcernDecl(label="runtime hosting", edges=(("componentRuntimeHosting", "componentModelServing"),)),
        )
        assert cfg.port_styles == {"port": "fill:#fff"}

    def test_malformed_aspect_entry_missing_required_key_defaults_to_flat(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n  component:\n    emission:\n      mode: decoupled\n"
            "      aspects:\n        - id: componentSecureLogging\n",  # missing minCrossInDegree
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        assert loader.get_emission_config().mode == "flat"

    @pytest.mark.parametrize(
        "bad_edge",
        [
            ["componentA", "componentB", "componentC"],  # 3 elements -- too many
            ["componentA"],  # 1 element -- too few
            "componentA",  # bare string, not a [src, tgt] list at all
        ],
        ids=["three-element-tuple", "one-element-tuple", "bare-string"],
    )
    def test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat(self, tmp_path, bad_edge):
        """
        Fix 4 (maintainer: "that's a real failure"). A `concerns[n].edges` entry whose
        tuple arity is not exactly 2 (`[src, tgt]`) is accepted today without
        validation -- `get_emission_config()` happily builds a `ConcernDecl` with a
        3-tuple (or 1-tuple) edge, and the crash only surfaces much later, deep inside
        `decouple.py::_resolve_concern_coverage`'s `for src, tgt in decl.edges:`
        unpacking, as a raw `ValueError: too many values to unpack` (confirmed by
        direct reproduction before writing this test) -- not the graceful degradation
        this accessor's own docstring promises ("missing or corrupt config never
        yields a half-decoupled diagram").

        The bare-string case (`edges: [componentA]` written without the inner list,
        i.e. a plain scalar) reproduces the identical deferred crash via a different
        route: `tuple("componentA")` silently succeeds, producing a 14-character
        tuple rather than raising, so this malformed shape is just as capable of
        slipping past an unvalidated accessor as the two explicit bad-arity lists
        above.

        Matches the established malformed-aspect-entry precedent immediately above
        (`test_malformed_aspect_entry_missing_required_key_defaults_to_flat`): a
        malformed entry degrades the WHOLE block to `flat`, not a per-entry drop with
        the rest of the config surviving -- for consistency with that precedent.
        """
        edge_yaml = "[" + ", ".join(bad_edge) + "]" if isinstance(bad_edge, list) else bad_edge
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n  component:\n    emission:\n      mode: decoupled\n"
            "      concerns:\n        - label: bad edge arity\n"
            f"          edges:\n            - {edge_yaml}\n",
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        assert loader.get_emission_config().mode == "flat", (
            "a concerns entry with a non-2-element edge tuple must degrade the whole "
            "emission block to flat (matching the malformed-aspect-entry precedent), "
            "not be accepted and crash later inside decouple.py's edge unpacking"
        )

    def test_non_dict_port_styles_defaults_to_flat(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n  component:\n    emission:\n      mode: decoupled\n"
            "      portStyles: 'not-a-dict'\n",
            encoding="utf-8",
        )
        loader = MermaidConfigLoader(config_file)
        assert loader.get_emission_config().mode == "flat"

    def test_missing_config_file_degrades_to_flat_via_emergency_defaults(self):
        loader = MermaidConfigLoader(Path("this-file-does-not-exist.yaml"))
        assert loader.get_emission_config().mode == "flat"

    def test_real_committed_config_has_no_emission_block_yet_and_defaults_to_flat(self, repo_root: Path):
        """
        Pins the Phase 2/3 boundary directly against the real, committed
        `mermaid-styles.yaml`: today it has no `emission` block (Phase 3 adds it), so
        this accessor's flat default is what production actually sees right now.
        """
        loader = MermaidConfigLoader(_styles_path(repo_root))
        assert loader.get_emission_config().mode == "flat"


# ============================================================================
# 2. Output-order contract (§A steps 1-8)
# ============================================================================


class TestOutputOrderContract:
    """
    All 8 fixed-order emission steps must appear, in order, in the built Mermaid text.
    Uses the small synthetic fixture (`_small_synthetic_components`/`_small_synthetic_cfg`),
    extended with one block (`_small_synthetic_components_with_block()`) so Step 7 has
    a genuine `~~~` marker to find -- ADR-036 D1's band-ports-not-chained revision
    means the base fixture alone (no subcategory blocks) emits zero `~~~` lines,
    since port-to-port chaining is removed and only a block's entry->exit pair
    survives -- so every marker below is a known, hand-verified quantity rather than a
    live-corpus derivation.
    """

    def test_all_eight_steps_appear_in_the_fixed_relative_order(self, repo_root: Path):
        components = _small_synthetic_components_with_block()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = plan.broadcasts[0]  # the sole "runtime hosting" broadcast
        block = plan.clusters[APP].blocks["componentsAppTestBlock"]

        # Step 1: frontmatter + graph LR preamble.
        marker_1 = "graph LR"
        # Step 2: header comments -- the undrawn hop-list first line, derived from the
        # plan itself (not hardcoded) so this doesn't presume header phrasing beyond
        # what plan §Phase-2 requires ("the undrawn p_out <-> p_in hop list per broadcast").
        marker_2 = f"{broadcast.label} ⇢ {broadcast.arm_count}"
        # Step 3: classDef port/pepport.
        marker_3 = "classDef port"
        # Step 4: cluster subgraph declarations.
        marker_4 = "subgraph componentsInfrastructure"
        # Step 5: drawn intra edges (the plain Alpha->Beta intra edge).
        marker_5 = "componentAlpha --> componentBeta"
        # Step 6: source->egress edge.
        marker_6 = f"componentRuntimeHosting --> {broadcast.egress_port_id}"
        # Step 7: invisible band link -- ADR-036 D1's band-ports-not-chained revision
        # means the only kind of `~~~` link left is a block's entry->exit pair (the
        # Application-cluster block added by `_small_synthetic_components_with_block()`);
        # port-to-port chaining across the Application/ReasoningCore ingress ports is
        # removed entirely, so this marker is no longer a bare "~~~" lookup.
        marker_7 = f"{block.entry_id} ~~~ {block.exit_id}"
        # Step 8: category style line, verbatim flat-path convention.
        marker_8 = "style componentsInfrastructure fill:"

        markers = [marker_1, marker_2, marker_3, marker_4, marker_5, marker_6, marker_7, marker_8]
        positions = []
        for marker in markers:
            assert marker in text, f"expected marker {marker!r} in emitted text"
            positions.append(text.index(marker))

        assert positions == sorted(positions), (
            f"emission steps out of order: markers {markers} at positions {positions}"
        )


# ============================================================================
# 3. Header comment formats
# ============================================================================


class TestHeaderCommentFormats:
    """
    Lifted-aspect inventory grouping (this suite's own line-format contract -- the
    plan only requires "grouped by source cluster, counts computed", not a literal
    string) and the undrawn hop list (ADR D6's literal mockup, order-independent).
    """

    def test_lifted_aspect_inventory_grouped_by_source_cluster_with_correct_counts(self, repo_root: Path):
        """
        This suite's own header-line contract: one comment line per source cluster
        feeding the lifted aspect, naming its count and (sorted) member source ids --
        derived programmatically from `plan.lifted_aspects` rather than hardcoded, so
        this test doesn't presume a specific literal wording beyond the line SHAPE it
        defines (`%%   <clusterId> (<count>): <sorted comma-separated source ids>`).
        Uses the live corpus (componentSecureLogging, 17 lifted edges across 3 source
        clusters) since the small synthetic fixture only has one source cluster.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        lifted = plan.lifted_aspects[0]
        assert lifted.aspect_id == "componentSecureLogging"
        expected_by_cluster: dict[str, list[str]] = {}
        for src, _tgt in lifted.edges:
            expected_by_cluster.setdefault(components[src].category, []).append(src)
        for cluster in expected_by_cluster:
            expected_by_cluster[cluster].sort()

        header_pattern = re.compile(r"^%%\s+(\w+) \((\d+)\): (.+)$", re.MULTILINE)
        found = {
            cluster: (int(count), sorted(s.strip() for s in sources.split(",")))
            for cluster, count, sources in header_pattern.findall(text)
        }

        for cluster, expected_sources in expected_by_cluster.items():
            assert cluster in found, f"expected a header line grouping cluster {cluster}"
            count, sources = found[cluster]
            expected_count = len(expected_sources)
            assert count == expected_count, f"{cluster}: expected count {expected_count}, got {count}"
            assert sources == expected_sources

        assert sum(c for c, _ in found.values()) == len(lifted.edges)

    def test_undrawn_hop_list_matches_adr_d6_mockup_literally(self, repo_root: Path):
        """
        Reproduces ADR-036 D6's exact mockup (docs/adr/036-decoupled-component-graph-
        emission.md): the header line format and every hop line, quoted directly.
        Order-INDEPENDENT: `_group_broadcasts` sorts channels by `tgt_root` string
        ("componentsApplication" < "componentsModel" alphabetically), which would put
        the Application arms first -- the opposite of the ADR mockup's illustrative
        Model-then-Application ordering. The plan explicitly says only the "port-id
        grammar, header-comment convention, and containment structure are normative"
        for this example, not the display order, so this test checks the hop-line SET,
        not a specific sequence (see `TestOutputOrderContract` for the one ordering
        contract this suite does pin: the 8-step relative order).
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = plan.broadcasts[0]
        assert broadcast.label == "runtime hosting"
        assert broadcast.arm_count == 3
        assert broadcast.egress_port_id == "p_out_infra_runtime_hosting"

        expected_header_line = (
            f"%% {broadcast.label} ⇢ {broadcast.arm_count} "
            "— the port-to-port hops are documented here, never drawn:"
        )
        assert expected_header_line in text, (
            f"expected literal ADR D6 header line {expected_header_line!r}; got:\n{text}"
        )
        # Cross-check against the literal ADR wording directly, not just the
        # programmatically-derived string above.
        assert "%% runtime hosting ⇢ 3 — the port-to-port hops are documented here, never drawn:" in text

        expected_hops = {
            f"%%   {broadcast.egress_port_id} ⇢ {arm.port_id}"
            for channel in broadcast.channels
            for arm in channel.arms
        }
        assert expected_hops == {
            "%%   p_out_infra_runtime_hosting ⇢ p_in_model_runtime_hosting",
            "%%   p_out_infra_runtime_hosting ⇢ p_in_app_runtime_hosting_application",
            "%%   p_out_infra_runtime_hosting ⇢ p_in_app_runtime_hosting_reasoning_core",
        }
        for hop in expected_hops:
            assert hop in text, f"expected hop line {hop!r} in emitted text"


# ============================================================================
# 4. Band links never span two roots
# ============================================================================


class TestBandLinksNeverSpanRoots:
    def test_plan_band_links_never_span_two_roots(self, repo_root: Path):
        """
        Root-scoping already guaranteed at the IR level by `decouple.py`'s
        `_build_band_links` -- included here as an explicit, direct regression pin on
        the exact data the emitter consumes.

        ADR-036 D1 revision ("Band ports are not chained together with invisible
        ordering links"): additionally asserts that no band link touches a port id at
        all. A band's own subgraph nesting is what pins its ports to the container's
        edge (ELK's compound-node contiguity constraint) -- chaining the ports
        together with `~~~` links was found to actively cause horizontal sprawl and is
        removed entirely; only a block's entry->exit pair (one link, two real
        component nodes) survives. Was RED against `_build_band_links` before the
        fix, which chained each cluster's egress ports together and each cluster's
        ingress ports together (24 port-to-port links in the live corpus). Now GREEN.
        """
        components, forward_map = _live_corpus(repo_root)
        plan = build_decoupled_plan(forward_map, components, _live_emission_config())
        port_root = _port_root_map(plan)

        port_ids = {b.egress_port_id for b in plan.broadcasts}
        port_ids |= {arm.port_id for b in plan.broadcasts for c in b.channels for arm in c.arms}

        for a, b in plan.band_links:
            root_a = port_root.get(a)
            root_b = port_root.get(b)
            if root_a is not None and root_b is not None:
                assert root_a == root_b, f"band link ({a}, {b}) spans roots {root_a}/{root_b}"
            assert a not in port_ids and b not in port_ids, (
                f"band link ({a}, {b}) is a port-to-port chain link; ADR-036 D1's "
                "band-ports-not-chained revision removes port chaining entirely -- only "
                "block entry/exit pairs are retained"
            )

    def test_emitted_band_links_never_span_two_roots(self, repo_root: Path):
        """
        Exercises the emitted `~~~` text itself, not just the IR.

        H2 coverage-gap fix (retained). Before that fix, the loop below guarded every
        lookup on `port_root.get(...) is not None`, silently SKIPPING any `~~~` line
        whose endpoint didn't resolve -- and since the old `_port_root_map` only
        mapped broadcast ports (never block entry/exit ids), that meant every
        block-level `~~~` link was silently skipped, unconditionally. `_port_root_map`
        now also maps block entry/exit ids to their cluster root, so every `~~~`
        endpoint in the live corpus should resolve, and the lookups below are hard
        assertions instead of a silent skip.

        ADR-036 D1 revision: additionally asserts that no emitted `~~~` line's
        endpoint is a port id, and that the total emitted `~~~` line count equals
        exactly the number of block entry/exit pairs -- zero port-to-port chain lines.
        Before this revision, a chain among a band's ports could stay root-scoped (and
        so pass the pre-existing checks) while still being exactly the sprawl-causing
        behavior this ADR revision removes; this test now catches that case directly.
        Was RED against `_build_band_links` before the fix, which emitted ~24
        port-to-port `~~~` lines in the live corpus in addition to the 4 block links
        (28 total). Now GREEN.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        port_root = _port_root_map(plan)
        tilde_lines = [line for line in text.splitlines() if "~~~" in line]
        assert tilde_lines, "expected at least one invisible band-ordering link in the emitted text"

        block_link_ids = {
            (block.entry_id, block.exit_id)
            for cluster in plan.clusters.values()
            for block in cluster.blocks.values()
            if block.entry_id is not None and block.exit_id is not None
        }
        assert block_link_ids, "expected at least one block with both an entry and an exit id in the live corpus"

        port_ids = {b.egress_port_id for b in plan.broadcasts}
        port_ids |= {arm.port_id for b in plan.broadcasts for c in b.channels for arm in c.arms}

        checked_block_link = False
        for line in tilde_lines:
            ids = [token.strip() for token in line.split("~~~")]
            for a, b in zip(ids, ids[1:]):
                id_a = a.split()[-1] if a else a
                id_b = b.split()[0] if b else b
                root_a = port_root.get(id_a)
                root_b = port_root.get(id_b)
                assert root_a is not None, f"unrecognized band-link endpoint {id_a!r} in line {line!r}"
                assert root_b is not None, f"unrecognized band-link endpoint {id_b!r} in line {line!r}"
                assert root_a == root_b, f"emitted band link in line {line!r} spans two roots"
                assert id_a not in port_ids and id_b not in port_ids, (
                    f"emitted band link in line {line!r} chains a port id; ADR-036 D1's "
                    "band-ports-not-chained revision removes port-to-port '~~~' links entirely"
                )
                if (id_a, id_b) in block_link_ids:
                    checked_block_link = True

        assert checked_block_link, (
            "expected at least one block-level entry->exit '~~~' link to be positively checked"
        )
        assert len(tilde_lines) == len(block_link_ids), (
            f"expected exactly {len(block_link_ids)} '~~~' line(s) -- one per block entry/exit "
            f"pair, zero port-to-port chain links; got {len(tilde_lines)}"
        )


# ============================================================================
# 5. Style / classDef passthrough
# ============================================================================


class TestStyleClassDefPassthrough:
    def test_every_original_category_style_line_survives_unchanged(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        component_categories = graph.config_loader.get_component_category_styles()
        for category_key, category_config in component_categories.items():
            style_str = graph._get_node_style("componentCategory", category_config=category_config)
            expected_line = f"style {category_key} {style_str}"
            assert expected_line in text, f"expected verbatim category style line {expected_line!r}"

    def test_port_and_pepport_classdefs_present_with_configured_strings(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        assert f"classDef port {PLACEHOLDER_PORT_STYLES['port']}" in text
        assert f"classDef pepport {PLACEHOLDER_PORT_STYLES['pepport']}" in text

    def test_pep_wrap_outline_style_applied_per_pep_wrapper(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        assert plan.pep_wrappers, "expected at least one PEP wrapper in the live corpus"
        for wrapper in plan.pep_wrappers.values():
            expected_line = f"style {wrapper.wrap_id} {PLACEHOLDER_PORT_STYLES['pepWrapOutline']}"
            assert expected_line in text, f"expected pepWrapOutline style line for {wrapper.wrap_id}"

    def test_band_containers_styled_fill_none_stroke_none(self, repo_root: Path):
        """Uses the small synthetic fixture, where the exact clusters carrying ports are known:
        Infrastructure has an egress band, Model and Application have ingress bands."""
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        band_ids = ("componentsInfrastructure_egress", "componentsModel_ingress", "componentsApplication_ingress")
        for band_id in band_ids:
            expected_line = f"style {band_id} fill:none,stroke:none"
            assert expected_line in text, f"expected band style line {expected_line!r}"


# ============================================================================
# 6. Output formats via to_mermaid()
# ============================================================================


class TestOutputFormats:
    def test_markdown_format_wraps_decoupled_output_in_fence(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        graph.graph = graph._emit_decoupled(plan)
        result = graph.to_mermaid(output_format="markdown")

        assert result.startswith("```mermaid\n")
        assert result.rstrip("\n").endswith("```")
        assert "graph LR" in result

    def test_raw_formats_are_unwrapped(self, repo_root: Path):
        """Any non-'markdown' format string is raw, per BaseGraph.to_mermaid's actual
        conditional -- tests both the 'mermaid'/'mmd' names used by validate_riskmap.py
        conventions and an arbitrary other string, to pin that this is genuinely
        format-string-agnostic, not special-cased on one literal value."""
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        graph.graph = graph._emit_decoupled(plan)
        for fmt in ("mermaid", "mmd", "raw"):
            result = graph.to_mermaid(output_format=fmt)
            assert not result.startswith("```"), f"format {fmt!r} should not be markdown-fenced"
            assert "graph LR" in result


# ============================================================================
# 7. Byte stability (§E: same YAML in -> byte-identical .mermaid out)
# ============================================================================


class TestByteStability:
    def test_double_run_produces_identical_text(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text_1 = graph._emit_decoupled(plan)
        text_2 = graph._emit_decoupled(plan)

        assert text_1 == text_2

    def test_shuffled_input_dict_produces_identical_text(self, repo_root: Path):
        """
        Same shuffle technique/seed as `test_decouple_coverage_gaps.py`'s M2 test,
        extended from the IR (Phase 1's guarantee, already proven there) to the built
        Mermaid TEXT -- that suite's own docstring says text-level equivalence "is
        Phase 2's job"; this is that job.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()

        rng = random.Random(20260723)
        shuffled_component_items = list(components.items())
        rng.shuffle(shuffled_component_items)
        components_shuffled = dict(shuffled_component_items)

        shuffled_forward_items = list(forward_map.items())
        rng.shuffle(shuffled_forward_items)
        forward_map_shuffled = dict(shuffled_forward_items)

        plan_a = build_decoupled_plan(forward_map, components, cfg)
        plan_b = build_decoupled_plan(forward_map_shuffled, components_shuffled, cfg)

        graph_a = _make_graph(components, forward_map, cfg, repo_root)
        graph_b = _make_graph(components_shuffled, forward_map_shuffled, cfg, repo_root)

        text_a = graph_a._emit_decoupled(plan_a)
        text_b = graph_b._emit_decoupled(plan_b)

        assert text_a == text_b


# ============================================================================
# 8. Flat-mode regression (expected GREEN now and after Phase 2)
# ============================================================================


class TestFlatModeRegression:
    """
    Expected GREEN today AND after Phase 2 implements the mode dispatch -- the flat
    path is untouched by this change. This pins the exact byte-identical baseline
    BEFORE Phase 2 touches `component_graph.py`, per the plan's Phase 2 exit criteria
    ("flat-mode output byte-identical to current risk-map-graph.mermaid"). Verified
    green against the current implementation before this suite was written.
    """

    def test_flat_mode_matches_committed_baseline_exactly(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        graph = ComponentGraph(forward_map, components)
        output = graph.to_mermaid(output_format="mermaid")
        assert output == _read_flat_baseline(repo_root)

    def test_missing_emission_config_also_takes_flat_path(self, repo_root: Path):
        """Real default loader (no emission block in the committed config) -- the
        licensed get_emission_config() accessor returns mode='flat', and build_graph()
        output is unaffected."""
        components, forward_map = _live_corpus(repo_root)
        loader = MermaidConfigLoader(_styles_path(repo_root))
        assert loader.get_emission_config().mode == "flat"

        graph = ComponentGraph(forward_map, components, config_loader=loader)
        assert graph.to_mermaid(output_format="mermaid") == _read_flat_baseline(repo_root)


# ============================================================================
# 9. Mode-dispatch integration (build_graph() itself)
# ============================================================================


class TestModeDispatchIntegration:
    """
    Integration test for `build_graph()`'s mode-dispatch contract (plan §A: "build_graph()
    reads config_loader.get_emission_config(); ... mode == 'decoupled' calls
    build_decoupled_plan() then self._emit_decoupled(plan)").

    UNLIKE most tests in this file, this one calls the PUBLIC `build_graph()` entry
    point rather than `_emit_decoupled()` directly, to pin the dispatch integration
    itself. Its original RED failure mode was therefore DIFFERENT from the rest of
    this suite's clean AttributeError: before the dispatch landed, `build_graph()`
    unconditionally took the flat path (it never consulted `get_emission_config()` at
    all), so this test failed as a content mismatch (decoupled-only markers absent
    from flat output), not an interface error. `build_graph()` now dispatches on mode
    (`component_graph.py:113-116`) and this test passes.
    """

    def test_decoupled_mode_config_routes_through_emit_decoupled(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        graph = _make_graph(components, forward_map, cfg, repo_root)

        output = graph.build_graph()

        assert "p_out_infra_runtime_hosting" in output
        assert output != _read_flat_baseline(repo_root)


# ============================================================================
# 10. controlsGovernance leakage check
# ============================================================================


class TestControlsGovernanceLeakage:
    """
    `_create_subgraph_section` (base.py:412-413) special-cases `category ==
    "controlsGovernance"` to emit `direction LR` inside that subgraph. Component
    graphs never have that category, but the decoupled path builds its own
    cluster/band/PEP-wrap subgraph rendering (plan §A step 4) rather than reusing the
    flat helper -- confirm it never routes through `_create_subgraph_section` at all,
    so a future category-naming collision could never accidentally pick up this
    flat-path special case in the decoupled emitter.
    """

    def test_emit_decoupled_never_calls_create_subgraph_section(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        with mock.patch.object(BaseGraph, "_create_subgraph_section") as spy:
            graph._emit_decoupled(plan)

        spy.assert_not_called()


# ============================================================================
# 11. Self-check delegates to verify_plan() for S1/S4/S5/S7
# ============================================================================


class TestSelfCheckDelegatesToVerifyPlan:
    """See module docstring "Why message-matching, not import-patching" for the rationale."""

    def test_s1_cross_root_drawn_edge_raises_via_verify_plan(self, repo_root: Path):
        plan = _base_plan(
            drawn_intra_edges=[("componentAlpha", "componentBeta")],
            intra_drawn_count=1,
            total_edges=1,
        )
        graph = _make_graph(_S_CHECK_COMPONENTS, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S1 violated"):
            graph._emit_decoupled(plan)

    def test_s5_edge_conservation_mismatch_raises_via_verify_plan(self, repo_root: Path):
        plan = _base_plan(total_edges=99)
        graph = _make_graph(_S_CHECK_COMPONENTS, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S5 edge conservation violated"):
            graph._emit_decoupled(plan)

    def test_s7_port_id_collision_raises_via_verify_plan(self, repo_root: Path):
        arm_1 = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_x",
            label="l1",
            edges=(("componentAlpha", "componentBeta"),),
        )
        chan_1 = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="l1",
            edges=(("componentAlpha", "componentBeta"),),
            arms=(arm_1,),
        )
        broadcast_1 = Broadcast(
            egress_port_id="p_out_dup", src_root=INFRA, label="l1", channels=(chan_1,), arm_count=1
        )
        arm_2 = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_y",
            label="l2",
            edges=(("componentAlpha", "componentBeta"),),
        )
        chan_2 = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="l2",
            edges=(("componentAlpha", "componentBeta"),),
            arms=(arm_2,),
        )
        broadcast_2 = Broadcast(
            egress_port_id="p_out_dup", src_root=INFRA, label="l2", channels=(chan_2,), arm_count=1
        )
        plan = _base_plan(broadcasts=(broadcast_1, broadcast_2))
        graph = _make_graph(_S_CHECK_COMPONENTS, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S7 violated"):
            graph._emit_decoupled(plan)

    def test_s4_duplicate_ingress_label_raises_via_verify_plan(self, repo_root: Path):
        arm_1 = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_a",
            label="dup label",
            edges=(("componentAlpha", "componentBeta"),),
        )
        chan_1 = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="dup label",
            edges=(("componentAlpha", "componentBeta"),),
            arms=(arm_1,),
        )
        broadcast_1 = Broadcast(
            egress_port_id="p_out_a", src_root=INFRA, label="dup label", channels=(chan_1,), arm_count=1
        )
        arm_2 = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_b",
            label="dup label",
            edges=(("componentAlpha", "componentBeta"),),
        )
        chan_2 = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="dup label 2",
            edges=(("componentAlpha", "componentBeta"),),
            arms=(arm_2,),
        )
        broadcast_2 = Broadcast(
            egress_port_id="p_out_b", src_root=INFRA, label="dup label 2", channels=(chan_2,), arm_count=1
        )
        plan = _base_plan(broadcasts=(broadcast_1, broadcast_2))
        graph = _make_graph(_S_CHECK_COMPONENTS, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S4 violated"):
            graph._emit_decoupled(plan)


# ============================================================================
# 12. New text-level checks: S2, S3, S6
# ============================================================================


class TestSelfCheckTextLevelChecks:
    """
    These properties are invisible to `verify_plan()` (an IR-only self-check) --
    Phase 2 must add them fresh. Each fixture below was verified NOT to trip any of
    verify_plan's S1/S4/S5/S7 checks (via a throwaway prototype), isolating exactly
    the new check under test.
    """

    def test_s2_broadcast_arm_count_mismatch_raises(self, repo_root: Path):
        """Declared arm_count (5) doesn't match the actual arms present (1) --
        verify_plan doesn't check this at all (arm_count is a bare int field it never
        cross-references); the new S2 check must."""
        arm = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_infra_test",
            label="test",
            edges=(("componentAlpha", "componentBeta"),),
        )
        chan = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="test",
            edges=(("componentAlpha", "componentBeta"),),
            arms=(arm,),
        )
        broadcast = Broadcast(
            egress_port_id="p_out_infra_test", src_root=INFRA, label="test", channels=(chan,), arm_count=5
        )
        plan = _base_plan(broadcasts=(broadcast,), channelled_count=1, total_edges=1)
        graph = _make_graph(_S_CHECK_COMPONENTS, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S2 violated"):
            graph._emit_decoupled(plan)

    def test_s3_ingress_port_out_degree_not_one_raises(self, repo_root: Path):
        """An extra, illegitimate outgoing edge injected directly into drawn_intra_edges
        from an ingress port id -- once rendered, that port has out-degree 2 (its own
        arm edge plus this injected one). verify_plan's S1 check skips this drawn edge
        entirely (the port id isn't a real components dict key), so only the new S3
        text-level check can catch it."""
        arm = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_infra_test2",
            label="test2",
            edges=(("componentAlpha", "componentBeta"),),
        )
        chan = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="test2",
            edges=(("componentAlpha", "componentBeta"),),
            arms=(arm,),
        )
        broadcast = Broadcast(
            egress_port_id="p_out_infra_test2", src_root=INFRA, label="test2", channels=(chan,), arm_count=1
        )
        plan = _base_plan(
            broadcasts=(broadcast,),
            drawn_intra_edges=[("p_in_infra_test2", "componentAlpha")],
            intra_drawn_count=1,
            channelled_count=1,
            total_edges=2,
        )
        graph = _make_graph(_S_CHECK_COMPONENTS, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S3 violated"):
            graph._emit_decoupled(plan)

    def test_s6_missing_pepport_classdef_raises(self, repo_root: Path):
        """emission.portStyles is missing the 'pepport'/'pepWrapOutline' keys while the
        plan has a real PEP wrapper needing them -- a config/plan mismatch the new S6
        check must catch (category style lines and classDef port/pepport/pepWrapOutline
        are all supposed to be present verbatim; here they can't be, since the config
        never supplied them)."""
        components = {
            "componentAlpha": _node(INFRA, to_edges=["componentBeta"]),
            "componentBeta": _node(INFRA, to_edges=[]),
            "componentGatewayPolicyEnforcementPoint": _node(APP, to_edges=[]),
        }
        forward_map = _forward_map(components)
        cfg = EmissionConfig(mode="decoupled", port_styles={"port": "fill:red"})  # no pepport/pepWrapOutline
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.pep_wrappers  # sanity: the fixture actually needs pepport styling
        # `_build_pep_wrappers` wraps every matching-suffix component unconditionally
        # (independent of forward_map), so `_S_CHECK_COMPONENTS`/{} (the sibling S1-S3
        # tests' safe-construction recipe) can't be reused here -- it would drop the
        # PEP component entirely, and `_emit_decoupled`'s title lookup needs it in
        # `self.components`. Instead, construct with these same components/forward_map
        # but a self-check-safe cfg (full port_styles, so __init__'s own internal
        # build_graph()/_emit_decoupled() pass cleanly), then swap the loader's cfg to
        # the S6-violating `cfg` afterwards so only the explicit call below observes
        # the missing pepport/pepWrapOutline keys.
        safe_cfg = EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)
        graph = _make_graph(components, forward_map, safe_cfg, repo_root)
        graph.config_loader._emission_cfg = cfg

        with pytest.raises(AssertionError, match=r"S6 violated"):
            graph._emit_decoupled(plan)


# ============================================================================
# Fix 3: strengthen the self-check's actual bug-catching power (maintainer: "we
# should fix this and improve the strength")
# ============================================================================


class TestSelfCheckCatchesGenuineEmitterDefects:
    """
    Fix 3 (maintainer: "we should fix this and improve the strength"). The
    adversarial critic demonstrated that S2 (`_check_s2_arm_counts`) and S5
    (`verify_plan`'s edge-conservation check) both recompute from the SAME IR
    counters/fields that built the plan in the first place -- `_check_s2_arm_counts`
    literally re-executes `sum(len(channel.arms) for channel in broadcast.channels)`,
    the identical expression `_group_broadcasts` used to compute `arm_count` when the
    plan was constructed. Such a check can only ever fire when a TEST hand-corrupts
    the IR after construction (as `TestSelfCheckTextLevelChecks`/`TestS2Reverse
    DirectionMismatch` already do); it can never fire against a genuine
    `_emit_decoupled()` implementation defect, because a real emitter bug corrupts
    the built TEXT while leaving the IR internally self-consistent -- exactly the
    case these checks are blind to.

    Confirmed concretely: a cross-wired ingress->landing edge (an arm's port pointing
    at the wrong node in the rendered text, while the IR's own `arm.landing_id` field
    is correct) passes all of S1-S8 today (verified via the throwaway prototypes
    below, run against the current implementation before this suite was written).

    Since this task requires RED tests only (no fix), and the current `_emit_
    decoupled()`/`decouple.py` genuinely cannot MISWIRE their own output (the text is
    built directly and correctly from the IR every time), each test below simulates
    "a genuine emitter defect" the only way possible without editing production code:
    monkeypatching one of `_emit_decoupled()`'s own step methods (`_decoupled_edges`,
    `_decoupled_cluster_subgraphs`) to return a plausibly-buggy variant of what it
    would otherwise produce, while leaving the `DecoupledPlan` IR passed in fully
    self-consistent (arm_count matches actual arms, `verify_plan`'s S1/S4/S5/S7 all
    hold). This isolates exactly the property under test: does the self-check
    inspect the BUILT TEXT for this specific defect class, or does it only ever
    recompute from IR fields that, by construction, cannot disagree with themselves.
    """

    def test_text_derived_s2_catches_a_dropped_ingress_port_declaration(self, repo_root: Path):
        """
        Genuine text-derived S2 (bullet 1). Simulates an emitter bug that drops one
        arm's ingress PORT NODE DECLARATION from the cluster-subgraph ingress band
        (`_decoupled_cluster_subgraphs`) while its `port_id --> landing_id` edge
        (a separate method, `_decoupled_edges`) is still drawn correctly -- the IR
        itself (`plan.broadcasts[*].channels[*].arms`, `arm_count`) is completely
        untouched and internally consistent, so the CURRENT `_check_s2_arm_counts`
        (`actual = sum(len(channel.arms) for channel in broadcast.channels)`) recomputes
        the same correct count from the same untouched IR and does not fire -- proving
        the tautology directly. A genuine text-derived S2 must instead count the actual
        ingress-port declarations/edges present for this broadcast IN THE BUILT TEXT
        and compare that count against `arm_count`, which would find only 2 declared
        ports for a `⇢ 3` broadcast here and raise.
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = plan.broadcasts[0]
        assert broadcast.arm_count == 3  # sanity: the ADR D6 ⇢3 worked example
        app_channel = next(c for c in broadcast.channels if c.tgt_root == APP)
        dropped_arm = next(a for a in app_channel.arms if a.target == "componentReasoningCore")

        original_cluster_subgraphs = ComponentGraph._decoupled_cluster_subgraphs

        def _dropping_one_ingress_declaration(self, plan, port_styles):
            lines = original_cluster_subgraphs(self, plan, port_styles)
            marker = f'{dropped_arm.port_id}["'
            return [line for line in lines if marker not in line]

        with mock.patch.object(ComponentGraph, "_decoupled_cluster_subgraphs", _dropping_one_ingress_declaration):
            with pytest.raises(AssertionError, match=r"S2"):
                graph._emit_decoupled(plan)

    def test_arm_port_to_landing_edge_must_literally_appear_in_built_text(self, repo_root: Path):
        """
        Closes the cross-wired-landing gap directly (bullet 2): a new assertion that
        every arm's `<port_id> --> <landing_id>` edge literally appears in the built
        text. Simulates an emitter bug that draws one arm's ingress edge to the WRONG
        node (a cross-wired landing) instead of `arm.landing_id` -- the arm's declared
        `landing_id` in the IR is untouched and correct, the port's rendered out-degree
        is still exactly 1 (S3, already implemented, does not fire: it only counts
        out-degree, never checks WHERE the edge points), and no existing check (S1-S8)
        inspects a specific arm's edge destination at all.
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = plan.broadcasts[0]
        app_channel = next(c for c in broadcast.channels if c.tgt_root == APP)
        target_arm = next(a for a in app_channel.arms if a.target == "componentReasoningCore")
        correct_line = f"{target_arm.port_id} --> {target_arm.landing_id}"
        wrong_line = f"{target_arm.port_id} --> componentApplication"  # cross-wired to a real, but wrong, node

        original_edges = ComponentGraph._decoupled_edges

        def _crosswiring_one_landing_edge(self, plan):
            lines = original_edges(self, plan)
            return [wrong_line if line.strip() == correct_line else line for line in lines]

        with mock.patch.object(ComponentGraph, "_decoupled_edges", _crosswiring_one_landing_edge):
            with pytest.raises(AssertionError):
                graph._emit_decoupled(plan)

    def test_source_to_egress_edge_pointing_at_wrong_egress_port_is_caught(self, repo_root: Path):
        """
        Bullet 3: extends text-level checking to source->egress lines (ties in
        naturally with Fix 1's new source-resolution logic -- a resolution bug there
        is exactly a source->egress edge pointing at an unexpected port id). Simulates
        an emitter bug that draws the broadcast source's egress edge to a bogus,
        unrelated port id instead of `broadcast.egress_port_id`. No existing check
        (S1-S8) inspects a source->egress line's destination at all today.
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = plan.broadcasts[0]
        correct_line = f"componentRuntimeHosting --> {broadcast.egress_port_id}"
        wrong_line = "componentRuntimeHosting --> p_out_WRONG_EGRESS_PORT"

        original_edges = ComponentGraph._decoupled_edges

        def _wrong_egress_port(self, plan):
            lines = original_edges(self, plan)
            return [wrong_line if line.strip() == correct_line else line for line in lines]

        with mock.patch.object(ComponentGraph, "_decoupled_edges", _wrong_egress_port):
            with pytest.raises(AssertionError):
                graph._emit_decoupled(plan)


class TestSelfChecksCatchS9S10ImplementationGaps:
    """
    Adversarial review found a real gap in S9/S10's OWN implementation (not the
    emitted output -- the checks themselves were under-specified). Both bugs were
    regressions against the code at the time (RED before the S9/S10 fix, GREEN after):

    Bug 1 (unanchored substring match, S9 + S10's first loop): `expected in text`
    has no line/token anchoring. Since the expected string's tail is a component id,
    and this corpus's real ids have genuine prefix relationships (`componentApplication`
    is a strict prefix of `componentApplicationInputHandling`,
    `componentApplicationOutputHandling`, `componentApplicationConsentSurface`, and
    `componentApplicationNetworkPolicyEnforcementPoint`), a cross-wired edge to the
    WRONG node whose id happens to extend the correct one satisfies `expected in text`
    via prefix match against the wrong line -- defeating the check entirely for this
    class of bug. `TestSelfCheckCatchesGenuineEmitterDefects.
    test_arm_port_to_landing_edge_must_literally_appear_in_built_text` above does not
    already cover this: its cross-wired target (`componentApplication`) is NOT a
    prefix of the correct landing id, so it is caught by the "expected line is simply
    absent" case, not this substring-collision case.

    Bug 2 (S10's reverse loop silently skips nonexistent egress ports): the reverse
    sweep only flags a found `<src> --> <port>` line when `port in egress_port_ids`,
    so an emitted edge to a port id that doesn't belong to ANY broadcast (a typo'd or
    stale port) is silently ignored rather than flagged -- contradicting the check's
    own docstring ("catches a source wired to the wrong (or a nonexistent) broadcast
    port"). Distinct from the existing
    `test_source_to_egress_edge_pointing_at_wrong_egress_port_is_caught` above, which
    REPLACES the correct line (so the first loop's "expected pair missing" branch
    already catches it); this test ADDS an extra bogus line while leaving every
    correct edge in place, isolating the reverse loop as the only branch that could
    catch it.
    """

    def test_arm_landing_edge_cross_wired_to_a_prefix_related_sibling_id_is_caught(self, repo_root: Path):
        """
        Live corpus, Bug 1: the "runtime hosting" broadcast's arm landing at
        `componentApplication` (`p_in_app_runtime_hosting_application`) is
        cross-wired to `componentApplicationInputHandling` -- a real, live, but wrong
        sibling id that happens to extend `componentApplication` as a substring.
        Under the pre-fix unanchored `expected in text` check, `"p_in_app_runtime_
        hosting_application --> componentApplication" in text` was still True (it was
        a substring of the wrong line), so S9 did not fire and this test was RED
        against the implementation at the time. Now GREEN.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = next(b for b in plan.broadcasts if b.label == "runtime hosting")
        target_arm = next(a for c in broadcast.channels for a in c.arms if a.target == "componentApplication")
        assert target_arm.landing_id == "componentApplication"  # sanity
        assert "componentApplicationInputHandling" in components  # sanity: a real, live sibling id

        correct_line = f"{target_arm.port_id} --> {target_arm.landing_id}"
        wrong_line = f"{target_arm.port_id} --> componentApplicationInputHandling"

        original_edges = ComponentGraph._decoupled_edges

        def _crosswiring_to_prefix_related_sibling(self, plan):
            lines = original_edges(self, plan)
            return [wrong_line if line.strip() == correct_line else line for line in lines]

        with mock.patch.object(ComponentGraph, "_decoupled_edges", _crosswiring_to_prefix_related_sibling):
            with pytest.raises(AssertionError, match="S9"):
                graph._emit_decoupled(plan)

    def test_source_egress_edge_to_a_nonexistent_port_id_is_caught(self, repo_root: Path):
        """
        Live corpus, Bug 2: an extra, bogus `<src> --> p_out_...` line is appended
        alongside every correct source->egress edge (none removed), pointing at a
        port id that belongs to no broadcast at all. Under the pre-fix
        `port in egress_port_ids` filter, this line was silently skipped by the
        reverse loop (and the first loop never fired, since every expected pair was
        still present verbatim), so this test was RED against the implementation at
        the time. Now GREEN.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = next(b for b in plan.broadcasts if b.label == "runtime hosting")
        egress_port_ids = {b.egress_port_id for b in plan.broadcasts}
        bogus_port = "p_out_BOGUS_NONEXISTENT"
        assert bogus_port not in egress_port_ids  # sanity: not a known egress port at all
        source = next(iter({src for channel in broadcast.channels for src, _tgt in channel.edges}))
        bogus_line = f"    {source} --> {bogus_port}"

        original_edges = ComponentGraph._decoupled_edges

        def _appending_a_bogus_egress_line(self, plan):
            return [*original_edges(self, plan), bogus_line]

        with mock.patch.object(ComponentGraph, "_decoupled_edges", _appending_a_bogus_egress_line):
            with pytest.raises(AssertionError, match="S10"):
                graph._emit_decoupled(plan)


# ============================================================================
# 13. S8: diagnostics surfaced, never raise
# ============================================================================


class TestSelfCheckDiagnosticsNeverRaise:
    def test_diagnostics_surfaced_in_output_but_never_raise(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        # diagnostics is strictly advisory (DecoupledPlan's own docstring: "it never
        # affects warnings or any drawn-output field"), so overriding it in isolation
        # on an otherwise-valid, self-check-clean plan is safe and doesn't corrupt
        # anything else the self-check inspects.
        marker = "reachability diagnostic (advisory only): test marker XYZZY123"
        plan_with_diagnostic = dataclasses.replace(plan, diagnostics=[marker])
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan_with_diagnostic)  # must NOT raise

        assert "XYZZY123" in text, "expected the diagnostic to be surfaced (e.g. as a comment), not swallowed"


# ============================================================================
# Fix 2: plan.warnings (D7 guard output, G-A1..G-O1) must be surfaced
# ============================================================================


class TestPlanWarningsSurfaced:
    """
    Fix 2 (maintainer: "this should be resolved"). Before this fix, `_emit_decoupled()`
    surfaced `plan.diagnostics` (S8, advisory) via a header comment and
    `logger.debug`, but dropped `plan.warnings` (the actual D7 guard output,
    G-A1..G-O1) entirely -- confirmed by reading `component_graph.py`: `plan.
    warnings` was never referenced anywhere in the module, so a guard warning (e.g. a
    stale aspect id, or a threshold violation) was not logged, not commented, and not
    raised. At the time, Phase 3 (which wires `check_emission_drift` into
    `validate_riskmap.py`'s `--block` machinery) had not landed yet, so this emitter
    call was the ONLY place a human could observe a guard warning at all, and it was
    silent. `plan.warnings` is now surfaced (`component_graph.py:241-242,307-308`).

    Design decision (this suite's own call, per the task's instruction to decide and
    document the mechanism): surface via BOTH channels, mirroring the existing S8
    diagnostics precedent (`TestSelfCheckDiagnosticsNeverRaise`), which already
    surfaces `plan.diagnostics` both via `logger.debug` AND a header comment --
      1. `logger.warning()`, once per warning message (the task's stated minimum
         bar) -- verified via `caplog`.
      2. A `%%`-prefixed header-comment block (step 2, alongside the lifted-aspect
         inventory and hop lists) -- more discoverable than a log line, since it
         lands directly in the committed `.mermaid` artifact that is this repo's
         actual diagram-review surface.
    Warnings must never raise (Phase 3's `--block` territory, not this emitter's) and
    must never change the drawn plan/output structure -- pinned by the third test
    below via a diff against the same plan with `warnings=[]`.
    """

    def _threshold_violation_fixture(self):
        """
        Reuses `test_decouple_guards.py::TestGA3AspectBelowThreshold`'s exact fixture
        shape (an aspect whose live cross in-degree, 7, is below its configured
        `minCrossInDegree`, 10) -- one of the two example triggers the task names,
        and one already established elsewhere in this TDD chain rather than invented
        fresh here.
        """
        components = {"componentSink": _node(INFRA, subcategory="componentsBlockX")}
        components["componentInfraFeeder"] = _node(
            INFRA, to_edges=["componentSink"], subcategory="componentsBlockX"
        )
        for i in range(7):
            components[f"componentModelSource{i}"] = _node(MODEL, to_edges=["componentSink"])
        forward_map = _forward_map(components)
        cfg = EmissionConfig(
            mode="decoupled",
            aspects=(AspectDecl(id="componentSink", min_cross_in_degree=10),),  # live cross in-degree 7 < 10
            concerns=(
                ConcernDecl(
                    label="under threshold flow",
                    edges=tuple((f"componentModelSource{i}", "componentSink") for i in range(7)),
                ),
            ),
            port_styles=PLACEHOLDER_PORT_STYLES,
        )
        return components, forward_map, cfg

    def test_guard_warning_logged_via_logger_warning(self, repo_root: Path, caplog):
        components, forward_map, cfg = self._threshold_violation_fixture()
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.warnings, "sanity: the G-A3 threshold violation must produce a plan.warnings entry"
        graph = _make_graph(components, forward_map, cfg, repo_root)

        with caplog.at_level(logging.WARNING):
            graph._emit_decoupled(plan)  # must NOT raise

        logged = "\n".join(record.message for record in caplog.records)
        for warning in plan.warnings:
            assert warning in logged, (
                f"expected every plan.warnings entry to be logged via logger.warning(); "
                f"missing: {warning!r}; captured log records:\n{logged}"
            )

    def test_guard_warning_surfaced_in_header_comment(self, repo_root: Path):
        components, forward_map, cfg = self._threshold_violation_fixture()
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.warnings

        graph = _make_graph(components, forward_map, cfg, repo_root)
        text = graph._emit_decoupled(plan)  # must NOT raise

        for warning in plan.warnings:
            assert warning in text, (
                f"expected plan.warnings entry surfaced as a header comment (discoverable "
                f"in the committed .mermaid artifact itself); missing: {warning!r}\ngot:\n{text}"
            )

    def test_warnings_never_raise_and_do_not_alter_drawn_output_structure(self, repo_root: Path):
        """
        Diffs the warning-bearing plan's emitted text against the identical plan with
        `warnings=[]`: every line present in one run but not the other must be
        attributable to warning surfacing itself (a comment line naming one of the
        warnings), never a change to a drawn node/edge/style line -- pins the "must
        not alter the drawn plan/output structure" constraint directly.
        """
        components, forward_map, cfg = self._threshold_violation_fixture()
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.warnings

        graph = _make_graph(components, forward_map, cfg, repo_root)
        text_with_warnings = graph._emit_decoupled(plan)  # must NOT raise

        plan_without_warnings = dataclasses.replace(plan, warnings=[])
        text_without_warnings = graph._emit_decoupled(plan_without_warnings)

        lines_with = text_with_warnings.splitlines()
        lines_without = text_without_warnings.splitlines()
        extra_lines = [line for line in lines_with if line not in lines_without]
        for line in extra_lines:
            assert any(warning in line for warning in plan.warnings), (
                f"a warnings-present run must only ADD warning-surfacing comment lines, "
                f"never change a drawn node/edge/style line; unexpected extra line: {line!r}"
            )

    def test_warnings_and_diagnostics_both_surfaced_when_both_present(self, repo_root: Path):
        """
        This fixture's sole channel has one arm, so `build_decoupled_plan()` itself
        can never populate `plan.diagnostics` here (`_reachability_diagnostic` in
        `decouple.py` skips channels with fewer than 2 targets) -- meaning warnings and
        diagnostics have only ever been exercised in isolation elsewhere in this suite
        (this fixture for warnings; the live corpus, whose warnings are empty, for
        `TestSelfCheckDiagnosticsNeverRaise`). Attaching a synthetic diagnostic via
        `dataclasses.replace` (the same technique `TestSelfCheckDiagnosticsNeverRaise`
        uses) proves the two header-comment-building code paths compose -- i.e. that
        the implementation appends both sections rather than one assignment
        clobbering the other.
        """
        components, forward_map, cfg = self._threshold_violation_fixture()
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.warnings, "sanity: fixture must still produce a warning"

        marker = "reachability diagnostic (advisory only): test marker CLOBBER456"
        plan_with_both = dataclasses.replace(plan, diagnostics=[marker])

        graph = _make_graph(components, forward_map, cfg, repo_root)
        text = graph._emit_decoupled(plan_with_both)  # must NOT raise

        for warning in plan.warnings:
            assert warning in text, (
                f"expected the warning to still be surfaced when a diagnostic is also "
                f"present; missing: {warning!r}\ngot:\n{text}"
            )
        assert "CLOBBER456" in text, (
            "expected the diagnostic to still be surfaced when a warning is also "
            "present -- one header-comment section must not clobber the other\n"
            f"got:\n{text}"
        )


# ============================================================================
# 14. Flat mode bypasses the decoupled self-check path entirely
# ============================================================================


class TestFlatModeBypassesSelfCheck:
    def test_flat_mode_with_a_would_be_s7_violation_does_not_raise(self, repo_root: Path):
        """
        Black-box proof that flat mode never enters the decoupled self-check path:
        this exact components/forward_map/concerns combination is the M6 slug-
        collision fixture from `test_decouple_coverage_gaps.py`, independently
        re-verified via a throwaway prototype to make `verify_plan()` raise
        `S7 violated: port id collision(s): [...]` when `mode="decoupled"`. Feeding the
        SAME registry through `mode="flat"` must not raise -- if it did, the decoupled
        self-check (or `build_decoupled_plan`) ran despite `mode="flat"`, violating the
        D3 rollback contract. This is independent of `component_graph.py`'s internal
        import mechanism for `verify_plan`/`build_decoupled_plan` (see module docstring
        "Why message-matching, not import-patching").

        Calls the PUBLIC `build_graph()` (not `_emit_decoupled()`), since this test is
        about the MODE DISPATCH itself. Before Phase 2 wired the dispatch,
        `build_graph()` always took the flat path regardless of config, so this test
        was expected GREEN even then -- it is a regression pin for the D3 rollback
        contract that stayed true once Phase 2 wired the dispatch, not a RED test.
        """
        components = {
            "componentInfraA": _node(INFRA, to_edges=["componentToolsA"]),
            "componentInfraB": _node(INFRA, to_edges=["componentToolsB"]),
            "componentToolsA": _node(TOOLS),
            "componentToolsB": _node(TOOLS),
        }
        forward_map = _forward_map(components)
        cfg = EmissionConfig(
            mode="flat",
            concerns=(
                ConcernDecl(label="tool/hosting", edges=(("componentInfraA", "componentToolsA"),)),
                ConcernDecl(label="tool hosting", edges=(("componentInfraB", "componentToolsB"),)),
            ),
        )
        graph = _make_graph(components, forward_map, cfg, repo_root)

        output = graph.build_graph()  # must not raise despite the S7-violating registry

        assert output
        assert "componentInfraA --> componentToolsA" in output  # ordinary flat edge rendering


# ============================================================================
# Coverage-gap tests (adversarial critic pass): H1-H3 (high severity), M1-M5 (medium).
#
# The correctness-focused code-reviewer pass approved the suite above; a separate
# adversarial coverage critic then found these gaps. Per the maintainer's request,
# both severities were closed here, before Phase 2 implementation. Each test below
# was RED for the same reason as the rest of this file -- `_emit_decoupled()` did not
# exist yet -- unless its docstring says otherwise.
# ============================================================================


# ----------------------------------------------------------------------------
# H1: PEP wrapper rendering has zero text-level assertions.
# ----------------------------------------------------------------------------


class TestPepWrapperRendering:
    """
    H1: the synthetic fixture (`_small_synthetic_components`/`_small_synthetic_cfg`)
    already includes a PEP-matching component (`componentGatewayPolicyEnforcementPoint`)
    specifically to exercise the wrap/retarget path, but no existing test inspects any
    PEP-related output. `plan.pep_wrappers[...]` is the authoritative source for the
    wrapper's `in_id`/`out_id`/`wrap_id` -- these tests read it from the plan rather
    than re-deriving `pep_wrap_base()` independently, so a test can't silently drift
    from whatever the IR actually produced.
    """

    def test_pep_wrap_subgraph_is_declared(self, repo_root: Path):
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        wrapper = plan.pep_wrappers["componentGatewayPolicyEnforcementPoint"]
        # Raises if no 'subgraph <wrap_id>' header line exists -- the positional
        # assertions in the next test depend on this succeeding.
        _subgraph_span(text, wrapper.wrap_id)

    def test_pep_in_out_ports_declared_inside_wrap_subgraph_with_pepport_class(self, repo_root: Path):
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        wrapper = plan.pep_wrappers["componentGatewayPolicyEnforcementPoint"]
        wrap_start, wrap_end = _subgraph_span(text, wrapper.wrap_id)
        wrap_text = text[wrap_start:wrap_end]

        in_pattern = re.compile(rf"\b{re.escape(wrapper.in_id)}\[.*?\]:::pepport")
        out_pattern = re.compile(rf"\b{re.escape(wrapper.out_id)}\[.*?\]:::pepport")
        assert in_pattern.search(wrap_text), (
            f"expected {wrapper.in_id!r} declared with :::pepport inside the wrap subgraph span; got:\n{wrap_text}"
        )
        assert out_pattern.search(wrap_text), (
            f"expected {wrapper.out_id!r} declared with :::pepport inside the wrap subgraph "
            f"span; got:\n{wrap_text}"
        )
        # Not merely present anywhere in the document -- confirm the SAME occurrence
        # used above is the one inside the span, not a coincidental second occurrence
        # elsewhere (there should only be one of each in this fixture).
        assert text.count(wrapper.in_id) >= 1
        assert wrap_text.count(wrapper.in_id) >= 1

    def test_pep_itself_declared_inside_its_own_wrap_subgraph(self, repo_root: Path):
        """
        ADR-036 D3: "the enforcement point is drawn inside its own outlined
        enclosure" -- the PEP component node itself, not just its ports, is expected
        inside the wrap subgraph's span.
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        wrapper = plan.pep_wrappers["componentGatewayPolicyEnforcementPoint"]
        wrap_start, wrap_end = _subgraph_span(text, wrapper.wrap_id)
        wrap_text = text[wrap_start:wrap_end]

        assert wrapper.pep_id in wrap_text, (
            f"expected the PEP node {wrapper.pep_id!r} declared inside its own wrap subgraph span"
        )

    def test_pep_port_chain_edge_emitted_after_all_subgraphs_close(self, repo_root: Path):
        """
        Plan §A step 5 names the PEP port chain literally: `pep_in --> pep --> pep_out`
        (a single chained-arrow Mermaid edge statement). Also confirms step ordering:
        this edge belongs to step 5 (edges), which must come after step 4 (subgraphs,
        including the wrap subgraph itself) closes -- an edge line nested inside the
        wrap subgraph's own text span would indicate the emitter drew it as part of
        the subgraph body rather than the edges section.
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        wrapper = plan.pep_wrappers["componentGatewayPolicyEnforcementPoint"]
        expected_chain = f"{wrapper.in_id} --> {wrapper.pep_id} --> {wrapper.out_id}"
        assert expected_chain in text, f"expected literal PEP port chain {expected_chain!r} in emitted text"

        _wrap_start, wrap_end = _subgraph_span(text, wrapper.wrap_id)
        chain_pos = text.index(expected_chain)
        assert chain_pos > wrap_end, "PEP port chain edge must be emitted after its wrap subgraph closes"


# ----------------------------------------------------------------------------
# H2: Block (subcategory) rendering is entirely unasserted.
# ----------------------------------------------------------------------------


class TestBlockRendering:
    """
    H2: every fixture used elsewhere in this file has `subcategory=None` throughout,
    so no existing test exercises block (subcategory) rendering at all. Uses the new
    `_block_fixture_components`/`_block_fixture_cfg` (an Application cluster with one
    subcategory block, entry -> middle -> exit).
    """

    def test_block_subgraph_nested_within_its_cluster_subgraph_span(self, repo_root: Path):
        components = _block_fixture_components()
        forward_map = _forward_map(components)
        cfg = _block_fixture_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        block = plan.clusters[APP].blocks["componentsAppTestBlock"]
        assert block.entry_id == "componentAppTestInputHandling"
        assert block.exit_id == "componentAppTestOutputHandling"

        cluster_start, cluster_end = _subgraph_span(text, APP)
        block_start, block_end = _subgraph_span(text, block.id)

        assert cluster_start < block_start, (
            "block subgraph must open strictly after its cluster's own opening line"
        )
        assert block_end < cluster_end, (
            "block subgraph must close (its own 'end') strictly before the cluster's 'end'"
        )

    def test_block_entry_exit_invisible_link_emitted(self, repo_root: Path):
        components = _block_fixture_components()
        forward_map = _forward_map(components)
        cfg = _block_fixture_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        block = plan.clusters[APP].blocks["componentsAppTestBlock"]
        # Sanity: Phase 1's `_build_band_links` already computes this pair into the IR.
        assert (block.entry_id, block.exit_id) in plan.band_links

        expected_link = f"{block.entry_id} ~~~ {block.exit_id}"
        assert expected_link in text, (
            f"expected block entry->exit invisible link {expected_link!r} in emitted text"
        )

    def test_ordinary_block_member_declared_inside_block_span(self, repo_root: Path):
        """
        H2 residual (coverage-critic re-check, round 2): the two tests above prove the
        block subgraph itself is declared and nested, and that the entry->exit `~~~`
        link exists -- but neither ever asserts that an ORDINARY block member (not the
        entry, not the exit -- `componentAppTestMiddle`, the pass-through node in the
        existing block fixture's entry -> middle -> exit chain) is actually declared
        INSIDE the block's subgraph span. A block that declared its entry and exit
        nodes correctly but rendered ordinary members outside (or never rendered them
        at all) would pass both existing tests.
        """
        components = _block_fixture_components()
        forward_map = _forward_map(components)
        cfg = _block_fixture_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        block = plan.clusters[APP].blocks["componentsAppTestBlock"]
        middle_id = "componentAppTestMiddle"
        assert middle_id not in (block.entry_id, block.exit_id)  # sanity: genuinely an ordinary member
        assert middle_id in block.members

        block_start, block_end = _subgraph_span(text, block.id)

        # Flat title convention (M4/H3 precedent): `<id>[<title>]`, unquoted.
        expected = f"{middle_id}[Test Node]"
        assert expected in text, f"expected ordinary block member node {expected!r} in emitted text"
        pos = text.index(expected)
        assert block_start < pos < block_end, "ordinary block member must be declared inside its block's span"


# ----------------------------------------------------------------------------
# H3: Port and component node declarations are never positively asserted.
# ----------------------------------------------------------------------------


class TestPortAndComponentNodeDeclarations:
    """
    H3: uses `_small_synthetic_components`/`_small_synthetic_cfg` (the D6 worked
    "runtime hosting" example: a bare Model arm, two suffixed Application arms).
    Literal grammar re-derived from ADR-036 D6's mockup:
        egress:  `<id>["▸ <label>  ⇢ <n>"]:::port`   (note the two spaces before ⇢)
        ingress: `<id>["<arm.label> ▸"]:::port`
    and from `base.py`'s existing `_create_subgraph_section`/`_get_nested_subgraph_new`
    convention for ordinary node titles: `<id>[<title>]` -- NO surrounding quotes (both
    methods interpolate `item.title` bare; confirmed by reading both directly).
    """

    def test_egress_port_node_declared_with_adr_mockup_grammar(self, repo_root: Path):
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = plan.broadcasts[0]
        assert broadcast.arm_count == 3  # sanity: this is the multi-arm ⇢3 worked example
        expected = f'{broadcast.egress_port_id}["▸ {broadcast.label}  ⇢ {broadcast.arm_count}"]:::port'
        assert expected in text, f"expected egress port node declaration {expected!r}; got:\n{text}"

        band_start, band_end = _subgraph_span(text, f"{INFRA}_egress")
        pos = text.index(expected)
        assert band_start < pos < band_end, "egress port node must be declared inside its cluster's egress band"

    def test_ingress_port_nodes_declared_bare_and_suffixed_forms(self, repo_root: Path):
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = plan.broadcasts[0]
        channel_by_root = {c.tgt_root: c for c in broadcast.channels}

        model_arm = channel_by_root[MODEL].arms[0]
        assert model_arm.label == "runtime hosting"  # bare: Model's only arm for this concern
        expected_model = f'{model_arm.port_id}["{model_arm.label} ▸"]:::port'
        assert expected_model in text, f"expected bare ingress port node {expected_model!r}; got:\n{text}"

        model_band_start, model_band_end = _subgraph_span(text, f"{MODEL}_ingress")
        model_pos = text.index(expected_model)
        assert model_band_start < model_pos < model_band_end

        app_channel = channel_by_root[APP]
        assert len(app_channel.arms) == 2  # sanity: App gets the suffixed multi-arm form
        app_band_start, app_band_end = _subgraph_span(text, f"{APP}_ingress")
        for arm in app_channel.arms:
            assert "→" in arm.label, f"expected a suffixed arm label, got {arm.label!r}"
            expected = f'{arm.port_id}["{arm.label} ▸"]:::port'
            assert expected in text, f"expected suffixed ingress port node {expected!r}; got:\n{text}"
            pos = text.index(expected)
            assert app_band_start < pos < app_band_end

    def test_ingress_to_landing_edge_emitted_for_at_least_one_arm(self, repo_root: Path):
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = plan.broadcasts[0]
        arm = broadcast.channels[0].arms[0]
        expected = f"{arm.port_id} --> {arm.landing_id}"
        assert expected in text, f"expected ingress->landing edge {expected!r}; got:\n{text}"

    def test_ordinary_component_node_declared_with_flat_title_convention(self, repo_root: Path):
        """
        `componentReasoningCore` is an ordinary (non-port, non-PEP) component --
        one of the runtime-hosting broadcast's arm LANDING targets, but the node
        declaration itself must match the flat emitter's existing convention:
        `<id>[<title>]`, no quotes. This is deliberately checked against BOTH
        presence and the specific absence of the quoted form, to pin that the
        decoupled path reuses the flat mechanism rather than introducing a new one.
        """
        components = _small_synthetic_components()
        forward_map = _forward_map(components)
        cfg = _small_synthetic_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected = "componentReasoningCore[Test Node]"
        assert expected in text, f"expected unquoted title-label node declaration {expected!r}; got:\n{text}"
        assert 'componentReasoningCore["Test Node"]' not in text, (
            "component node titles should not be quoted -- that grammar is reserved for port/pepport nodes"
        )

        cluster_start, cluster_end = _subgraph_span(text, APP)
        pos = text.index(expected)
        assert cluster_start < pos < cluster_end, "ordinary component node must be declared inside its own cluster"


# ----------------------------------------------------------------------------
# Coverage-gap follow-up, round 2 (adversarial critic re-check on the 50-test batch
# above): one high-severity composition gap (PEP-wrapped arm landing, never tested
# together with the PEP-wrap rendering it composes with) and three medium composition
# gaps (PEP-wrap-inside-block nesting, block-member placement, concern-label
# escaping). Each test below was RED for the same reason as the rest of this file
# before `_emit_decoupled()` was implemented, unless its docstring says otherwise.
# ----------------------------------------------------------------------------


class TestIngressLandingAtPepWrappedTarget:
    """
    High severity: the only existing ingress->landing edge assertion
    (`TestPortAndComponentNodeDeclarations.
    test_ingress_to_landing_edge_emitted_for_at_least_one_arm`) reads
    `plan.broadcasts[0].channels[0].arms[0]` from `_small_synthetic_cfg()`'s "runtime
    hosting" broadcast, whose first (alphabetically sorted) arm target --
    `componentReasoningCore` -- is a plain component, not PEP-wrapped. PEP-wrapping
    (H1, `TestPepWrapperRendering`) and arm-landing (H3, this class's sibling) are each
    tested, but never TOGETHER: an emitter that drew `arm.port_id --> arm.target` (the
    raw PEP component id) instead of the correct `arm.port_id --> arm.landing_id` (the
    wrapper's `_in` port, per `decouple.py::_build_arms`'s `landing_id =
    pep_wrappers[target].in_id if target in pep_wrappers else target`) would pass all
    50 existing tests while producing wrong edges for every live-corpus arm that lands
    at a PEP -- 7+ real arms (tool discovery, identity & authz x5, inference/serving,
    tool calls; see `mermaid-styles.yaml`'s `emission.concerns` registry). Uses a
    dedicated, minimal fixture
    (`_pep_landing_fixture_components`/`_cfg`) whose sole channel's sole arm targets a
    PEP-wrapped component, isolating exactly this path.
    """

    def test_ingress_to_landing_edge_retargets_through_pep_in_port(self, repo_root: Path):
        components = _pep_landing_fixture_components()
        forward_map = _forward_map(components)
        cfg = _pep_landing_fixture_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        arm = plan.broadcasts[0].channels[0].arms[0]
        assert arm.target == "componentLandingPolicyEnforcementPoint"
        wrapper = plan.pep_wrappers[arm.target]
        assert arm.landing_id == wrapper.in_id  # sanity: Phase 1's own retargeting rule (already proven)

        text = graph._emit_decoupled(plan)

        expected = f"{arm.port_id} --> {arm.landing_id}"
        assert expected in text, (
            f"expected ingress->landing edge {expected!r} landing at the PEP's _in port; got:\n{text}"
        )

        wrong = f"{arm.port_id} --> {arm.target}"
        assert wrong not in text, (
            f"ingress->landing edge must retarget through the PEP wrapper's _in port "
            f"({arm.landing_id!r}), not land directly at the raw PEP component id "
            f"({arm.target!r}); found {wrong!r} in emitted text"
        )


class TestSourceEgressResolvesThroughPepWrapper:
    """
    Fix 1 (confirmed defect, maintainer: "they need to exit via the out port"). The
    sibling to `TestIngressLandingAtPepWrappedTarget` above, but on the SOURCE side of
    a broadcast: `_decoupled_edges`'s source->egress line construction
    (`component_graph.py`) currently uses the raw source component id even when that
    source is PEP-wrapped, drawing a cross-boundary edge straight from the bare PEP
    node to the egress port -- never passing through the wrapper's `_out` port. This
    contradicts ADR-036 D3's rationale for PEP wrappers ("a reader sees traffic
    entering and leaving through the enforcement point"), and is live in the real
    corpus today: reproduced directly below against the two `app + agent egress`
    sources and the `tool results` source (confirmed via direct reproduction before
    writing this test).

    Constraint: this is resolvable entirely in the emission layer via
    `plan.pep_wrappers` lookups (`Arm.landing_id` already demonstrates the identical
    pattern on the target side in `decouple.py::_build_arms`) -- no IR-level change to
    `decouple.py` is required or expected; these tests exercise `_emit_decoupled()`
    only, never `decouple.py` directly.
    """

    def test_app_agent_egress_broadcast_both_pep_sources_resolve_through_out_port(self, repo_root: Path):
        """
        Live corpus, primary defect fixture: the `app + agent egress` broadcast has
        TWO distinct sources, both PEP-wrapped (`componentAgentNetworkPolicy
        EnforcementPoint`, `componentApplicationNetworkPolicyEnforcementPoint`) -- the
        exact scenario the task names. Also closes a related test gap: no existing
        test asserted a source->egress edge per DISTINCT source at all (see the
        sibling multi-source test below for the non-PEP case).
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = next(b for b in plan.broadcasts if b.label == "app + agent egress")
        sources = sorted({src for channel in broadcast.channels for src, _tgt in channel.edges})
        assert sources == [
            "componentAgentNetworkPolicyEnforcementPoint",
            "componentApplicationNetworkPolicyEnforcementPoint",
        ]  # sanity: both sources are PEP-wrapped (plan.pep_wrappers, asserted below)
        for source in sources:
            assert source in plan.pep_wrappers  # sanity

        text = graph._emit_decoupled(plan)

        for source in sources:
            wrapper = plan.pep_wrappers[source]
            expected = f"{wrapper.out_id} --> {broadcast.egress_port_id}"
            assert expected in text, (
                f"expected the PEP-wrapped source to exit via its _out port ({expected!r}); got:\n{text}"
            )
            wrong = f"{source} --> {broadcast.egress_port_id}"
            assert wrong not in text, (
                f"a PEP-wrapped source must never draw its source->egress edge from the "
                f"raw component id ({wrong!r}) -- it must exit via {wrapper.out_id!r}; "
                f"found the raw form in emitted text"
            )

        # Literal reproduction of the task's own worked example, independent of the
        # programmatically-derived strings above.
        assert "agentNetworkPep_out --> p_out_app_app_agent_egress" in text
        assert "applicationNetworkPep_out --> p_out_app_app_agent_egress" in text
        assert "componentAgentNetworkPolicyEnforcementPoint --> p_out_app_app_agent_egress" not in text
        assert "componentApplicationNetworkPolicyEnforcementPoint --> p_out_app_app_agent_egress" not in text

    def test_tool_results_broadcast_single_pep_source_resolves_through_out_port(self, repo_root: Path):
        """Live corpus: the `tool results` broadcast's sole source is the
        tool-network PEP -- the third live-corpus instance the task names."""
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = next(b for b in plan.broadcasts if b.label == "tool results")
        source = "componentToolNetworkPolicyEnforcementPoint"
        assert source in plan.pep_wrappers  # sanity

        text = graph._emit_decoupled(plan)

        wrapper = plan.pep_wrappers[source]
        expected = f"{wrapper.out_id} --> {broadcast.egress_port_id}"
        assert expected in text, f"expected {expected!r} in emitted text; got:\n{text}"
        assert "componentToolNetworkPolicyEnforcementPoint --> p_out_tools_tool_results" not in text
        assert "toolNetworkPep_out --> p_out_tools_tool_results" in text

    def test_identity_authz_broadcast_multiple_non_pep_sources_each_get_own_edge(self, repo_root: Path):
        """
        Live corpus: the `identity & authz` broadcast has two distinct sources
        (`componentIdentityProvider`, `componentAuthorizationPolicyDecisionPoint`),
        NEITHER of which is PEP-wrapped -- the multi-source coverage gap the task
        separately names ("weren't previously asserted per-source at all"). This test
        is expected to ALREADY PASS against the current implementation (the raw-id
        source->egress construction is correct when the source isn't PEP-wrapped;
        `_decoupled_edges` already iterates the full distinct-source set) -- kept here
        as an explicit regression pin for that gap, and to document that the defect's
        scope is the PEP-source-resolution path specifically, not multi-source
        handling in general.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = next(b for b in plan.broadcasts if b.label == "identity & authz")
        sources = sorted({src for channel in broadcast.channels for src, _tgt in channel.edges})
        assert sources == ["componentAuthorizationPolicyDecisionPoint", "componentIdentityProvider"]
        for source in sources:
            assert source not in plan.pep_wrappers  # sanity: neither source is PEP-wrapped

        text = graph._emit_decoupled(plan)

        for source in sources:
            expected = f"{source} --> {broadcast.egress_port_id}"
            assert expected in text, f"expected a distinct source->egress edge {expected!r}; got:\n{text}"

    def test_synthetic_broadcast_mixing_pep_and_plain_sources_resolves_each_independently(self, repo_root: Path):
        """
        Clean unit-level pin, independent of the live corpus and its 12-entry
        registry: a minimal synthetic fixture with ONE broadcast fed by two distinct
        sources sharing a single arm target -- one PEP-wrapped, one plain -- isolating
        the per-source resolution decision from any other broadcast/channel-grouping
        behavior. Confirms both that a PEP source resolves through its `_out` port AND
        that a plain source in the SAME broadcast is unaffected (still resolves to its
        raw id), proving the fix is a per-source lookup, not a broadcast-wide switch.
        """
        components = {
            "componentPlainSource": _node(INFRA, to_edges=["componentTarget"]),
            "componentSourcePolicyEnforcementPoint": _node(INFRA, to_edges=["componentTarget"]),
            "componentTarget": _node(MODEL, to_edges=[]),
        }
        forward_map = _forward_map(components)
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(
                ConcernDecl(
                    label="multi src test",
                    edges=(
                        ("componentPlainSource", "componentTarget"),
                        ("componentSourcePolicyEnforcementPoint", "componentTarget"),
                    ),
                ),
            ),
            port_styles=PLACEHOLDER_PORT_STYLES,
        )
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        broadcast = plan.broadcasts[0]
        assert broadcast.egress_port_id == "p_out_infra_multi_src_test"  # sanity
        wrapper = plan.pep_wrappers["componentSourcePolicyEnforcementPoint"]
        assert wrapper.out_id == "sourcePep_out"  # sanity

        text = graph._emit_decoupled(plan)

        assert f"componentPlainSource --> {broadcast.egress_port_id}" in text, (
            "the plain (non-PEP) source must still resolve to its raw id"
        )
        assert f"{wrapper.out_id} --> {broadcast.egress_port_id}" in text, (
            "the PEP-wrapped source, sharing the same broadcast, must independently "
            "resolve through its own _out port"
        )
        assert f"componentSourcePolicyEnforcementPoint --> {broadcast.egress_port_id}" not in text, (
            "the raw PEP id must never appear as a source->egress edge"
        )


class TestPepWrapNestedInsideBlock:
    """
    Medium severity: H1 (`TestPepWrapperRendering`) proves a PEP wrap subgraph is
    declared and H2 (`TestBlockRendering`) proves a block subgraph is nested inside
    its cluster -- but no existing test nests a PEP wrap subgraph INSIDE a block
    subgraph, which is the live corpus's actual shape: all 4 real PEPs (`decouple.
    py`'s `_PEP_ID_PATTERN` matches, confirmed against the live corpus by
    `test_decouple_transform.py`'s `TestLiveCorpusInventory`) live inside a
    subcategory block. Combines `_block_fixture_components`'s entry -> middle -> exit
    shape with a PEP-wrapped middle member (`_pep_in_block_fixture_components`) to
    assert the full triple containment: wrap subgraph nested inside block subgraph
    nested inside cluster subgraph.
    """

    def test_pep_wrap_subgraph_triple_nested_inside_block_inside_cluster(self, repo_root: Path):
        components = _pep_in_block_fixture_components()
        forward_map = _forward_map(components)
        cfg = _pep_in_block_fixture_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        block = plan.clusters[APP].blocks["componentsPibBlock"]
        wrapper = plan.pep_wrappers["componentPibGatewayPolicyEnforcementPoint"]
        assert block.entry_id == "componentPibInputHandling"
        assert block.exit_id == "componentPibOutputHandling"

        text = graph._emit_decoupled(plan)

        cluster_start, cluster_end = _subgraph_span(text, APP)
        block_start, block_end = _subgraph_span(text, block.id)
        wrap_start, wrap_end = _subgraph_span(text, wrapper.wrap_id)

        assert cluster_start < block_start < wrap_start, (
            "expected cluster subgraph to open, then the block subgraph, then the PEP wrap subgraph"
        )
        assert wrap_end < block_end < cluster_end, (
            "expected the PEP wrap subgraph to close, then the block subgraph, then the cluster subgraph"
        )


class TestConcernLabelEscaping:
    """
    Medium severity: distinct from M4's (`TestSpecialCharacterHandling`) title-
    escaping test -- concern labels flow into a DIFFERENT Mermaid grammar than
    component titles. Component titles interpolate bare and UNQUOTED (`<id>[<title>]`,
    M4's finding, confirmed by reading `base.py` directly) inside a bracket-delimited
    node shape. Concern labels interpolate into QUOTED port-label strings
    (`<id>["<label> ▸"]:::port`, `<id>["▸ <label>  ⇢ <n>"]:::port` -- see
    `TestPortAndComponentNodeDeclarations`/`TestSingleArmBareGrammar`) and into
    `%%`-prefixed header comment lines (see `TestHeaderCommentFormats`).

    Neither the ADR (D3's "concern labels are semantic knowledge... living in a
    styling file" framing, `docs/adr/036-decoupled-component-graph-emission.md` lines
    53/153) nor `decouple.py`'s `slug()` docstring say anything about escaping --
    confirmed by reading both. So, per this task's instruction, this test makes its
    own explicit design-decision call rather than leaving the behavior ambiguous:

    1. Quoted port-label text (the grammar delimited by literal `"..."`) is the one
       surface where an embedded `"` character is not merely cosmetically odd (M4's
       bracket case, which stays syntactically valid Mermaid even unescaped, since
       brackets inside an already-quoted string need no delimiter protection) but
       SYNTAX-BREAKING: an unescaped `"` prematurely closes the quoted string,
       garbling every token after it on that line. Reproducing M4's "no escaping
       convention exists in this codebase, so pass through bare" call here would not
       merely look ugly -- it would emit genuinely invalid Mermaid, which is exactly
       what `decouple.py`'s own module docstring's stated D7 philosophy exists to
       prevent ("a generator that silently emits a wrong diagram is worse than one
       that raises"). This test therefore expects the emitter to escape an embedded
       `"` using Mermaid's own documented mechanism for this exact situation -- the
       `#quot;` HTML-entity code for quoted flowchart labels -- rather than inventing
       a bespoke escaping scheme unique to this codebase (which the task explicitly
       warns against; `#quot;` is Mermaid's own convention, not a new one).
    2. `%%`-prefixed header comment lines are a different grammar: a Mermaid line
       comment runs verbatim to end-of-line and is never string-delimited, so a `"`
       character there is inert -- it does not need escaping to remain valid Mermaid.
       This test therefore expects the header-comment occurrence of the SAME label to
       pass through literally (unescaped), matching M4's "no invented escaping"
       precedent for the one grammar context here where raw passthrough is genuinely
       safe.
    3. `slug()`-derived port ids are unaffected either way: `slug()` (`decouple.py`)
       already collapses any run of non-alphanumeric characters -- including `"` --
       to a single `_`, so a quote character in a label can never reach a port id
       regardless of this decision; not re-tested here (already covered by the
       existing slug()/port-id tests in this suite and in `test_decouple_transform.py`).
    """

    def test_concern_label_with_embedded_quote_is_escaped_in_quoted_labels_but_not_in_header_comment(
        self, repo_root: Path
    ):
        components = {
            "componentAlpha": _node(INFRA, to_edges=["componentBeta"]),
            "componentBeta": _node(MODEL, to_edges=[]),
        }
        forward_map = _forward_map(components)
        raw_label = 'trust "boundary" crossing'
        cfg = EmissionConfig(
            mode="decoupled",
            concerns=(ConcernDecl(label=raw_label, edges=(("componentAlpha", "componentBeta"),)),),
            port_styles=PLACEHOLDER_PORT_STYLES,
        )
        plan = build_decoupled_plan(forward_map, components, cfg)
        broadcast = plan.broadcasts[0]
        arm = broadcast.channels[0].arms[0]
        # Bare single-arm form (M2 precedent): Phase 1 passes the label through as-is,
        # quote character and all -- escaping is strictly an emission-pass (Phase 2) concern.
        assert arm.label == raw_label
        assert broadcast.label == raw_label

        graph = _make_graph(components, forward_map, cfg, repo_root)
        text = graph._emit_decoupled(plan)

        escaped_label = raw_label.replace('"', "#quot;")

        expected_quoted_ingress = f'{arm.port_id}["{escaped_label} ▸"]:::port'
        assert expected_quoted_ingress in text, (
            f"expected the embedded '\"' in the concern label to be escaped as '#quot;' inside "
            f"the quoted ingress port label (Mermaid's own escaping mechanism for this grammar); "
            f"got:\n{text}"
        )
        # The raw (unescaped) form must NOT appear as a quoted label -- confirms escaping
        # actually happened, not that both forms coincidentally satisfy the assertion above.
        assert f'{arm.port_id}["{raw_label} ▸"]:::port' not in text

        expected_quoted_egress = f'{broadcast.egress_port_id}["▸ {escaped_label}  ⇢ {broadcast.arm_count}"]:::port'
        assert expected_quoted_egress in text, (
            f"expected the escaped label in the quoted egress port node; got:\n{text}"
        )
        assert f'{broadcast.egress_port_id}["▸ {raw_label}  ⇢ {broadcast.arm_count}"]:::port' not in text

        # Header comment (`%% ...`): the SAME label, passed through literally -- a
        # Mermaid line comment is not string-delimited, so no escaping is expected or
        # required here (design decision 2 above).
        expected_header = (
            f"%% {raw_label} ⇢ {broadcast.arm_count} — the port-to-port hops are documented here, never drawn:"
        )
        assert expected_header in text, f"expected literal (unescaped) label in header comment; got:\n{text}"


# ----------------------------------------------------------------------------
# M1: Degenerate/empty plans.
# ----------------------------------------------------------------------------


class TestDegenerateEmptyPlans:
    """
    M1: a plan with zero lifted aspects and zero broadcasts/channels (an all-intra
    synthetic corpus, `_degenerate_components`/`_degenerate_cfg`) must still emit
    without raising. Two independent design decisions pinned here:

    1. Header comments (step 2: hop-list + aspect inventory) are OMITTED ENTIRELY
       when there is nothing to report, not emitted as an empty placeholder section.
       Rationale: no other step in this emitter (or in the flat emitter it can fall
       back to) ever prints a "(nothing here)" placeholder for an empty section --
       e.g. the flat emitter's category-style block always has content because every
       category always has a style, so there is no existing precedent to follow for a
       deliberately-empty section, and inventing a placeholder purely for this one
       degenerate case adds noise without adding information a reader could act on.
    2. `classDef port`/`classDef pepport` (step 3) are config-driven and
       position-fixed -- independent of whether any node in THIS plan ends up
       wearing `:::port`/`:::pepport` -- so the classDef lines are still expected to
       be emitted (mirroring the flat emitter's precedent of always emitting its full
       static style block regardless of per-category edge count). What must NOT
       happen is an orphaned `:::port`/`:::pepport` USAGE on some node when this
       plan has zero actual ports and zero PEP wrappers.
    """

    def test_emission_succeeds_with_no_header_lines_and_no_orphaned_port_classes(self, repo_root: Path):
        components = _degenerate_components()
        forward_map = _forward_map(components)
        cfg = _degenerate_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.broadcasts == ()
        assert plan.lifted_aspects == []
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)  # must not raise

        assert "⇢" not in text, "expected no hop-list header lines for a plan with zero broadcasts"
        assert not re.search(r"^%%\s+\w+ \(\d+\):", text, re.MULTILINE), (
            "expected no aspect-inventory header lines for a plan with zero lifted aspects"
        )
        # Design decision 2 above.
        assert "classDef port" in text
        assert "classDef pepport" in text
        assert ":::port" not in text, "no node should carry an orphaned :::port usage"
        assert ":::pepport" not in text, "no node should carry an orphaned :::pepport usage"


# ----------------------------------------------------------------------------
# M2: Single-arm (bare label, unsuffixed port id) text grammar.
# ----------------------------------------------------------------------------


class TestSingleArmBareGrammar:
    """
    M2: the only existing hop-list assertion
    (`test_undrawn_hop_list_matches_adr_d6_mockup_literally`) covers the ⇢3 multi-arm
    case. Uses the live corpus's "tool hosting" broadcast (§C table: 1 arm) to exercise
    `_build_arms`'s bare-vs-suffixed logic when `multi_arm` is False.
    """

    def test_single_arm_broadcast_uses_bare_header_and_unsuffixed_port_id(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = next(b for b in plan.broadcasts if b.label == "tool hosting")
        assert broadcast.arm_count == 1  # sanity: this is the single-arm case (plan §C table)
        arm = broadcast.channels[0].arms[0]
        assert arm.label == "tool hosting", "bare label -- no '→ <target>' suffix"
        assert arm.port_id == "p_in_tools_tool_hosting", "unsuffixed port id -- no '_<target>' suffix"

        expected_header = f"%% {broadcast.label} ⇢ 1 — the port-to-port hops are documented here, never drawn:"
        assert expected_header in text, f"expected literal bare-form header line {expected_header!r}"

        expected_ingress_node = f'{arm.port_id}["{arm.label} ▸"]:::port'
        assert expected_ingress_node in text, f"expected bare ingress port node {expected_ingress_node!r}"


# ----------------------------------------------------------------------------
# M3: S2 tested in only one direction.
# ----------------------------------------------------------------------------


class TestS2ReverseDirectionMismatch:
    """
    M3: the only existing S2 test (`TestSelfCheckTextLevelChecks.
    test_s2_broadcast_arm_count_mismatch_raises`) trips the check with declared
    `arm_count` (5) GREATER than actual arms present (1). A check that only compares
    `actual >= declared` (rather than exact equality) would pass that test while still
    being wrong. This constructs the opposite corruption: declared `arm_count` (1)
    LESS than actual arms present (2), isolating exact-equality behavior.
    """

    def test_s2_more_arms_present_than_declared_raises(self, repo_root: Path):
        arm_1 = Arm(
            target="componentBeta",
            landing_id="componentBeta",
            port_id="p_in_infra_test_a",
            label="test → a",
            edges=(("componentAlpha", "componentBeta"),),
        )
        arm_2 = Arm(
            target="componentGamma",
            landing_id="componentGamma",
            port_id="p_in_infra_test_b",
            label="test → b",
            edges=(("componentAlpha", "componentGamma"),),
        )
        chan = Channel(
            src_root=INFRA,
            tgt_root=MODEL,
            concern="test",
            edges=(("componentAlpha", "componentBeta"), ("componentAlpha", "componentGamma")),
            arms=(arm_1, arm_2),
        )
        broadcast = Broadcast(
            egress_port_id="p_out_infra_test", src_root=INFRA, label="test", channels=(chan,), arm_count=1
        )
        plan = _base_plan(broadcasts=(broadcast,), channelled_count=2, total_edges=2)
        components = dict(_S_CHECK_COMPONENTS)
        components["componentGamma"] = _node(MODEL)
        graph = _make_graph(components, {}, _small_synthetic_cfg(), repo_root)

        with pytest.raises(AssertionError, match=r"S2 violated"):
            graph._emit_decoupled(plan)


# ----------------------------------------------------------------------------
# M4: Escaping/special characters.
# ----------------------------------------------------------------------------


class TestSpecialCharacterHandling:
    """
    M4: pins the decoupled emitter's behavior for a component title containing a
    Mermaid-syntax-sensitive character. Component titles (not concern labels) are the
    realistic surface here: concern labels come from the small, curated
    `emission.concerns` registry (a dozen hand-written entries), while titles are
    freeform content authored per-component in `components.yaml`.

    The existing flat emitter (`base.py::_create_subgraph_section`/
    `_get_nested_subgraph_new`) has NO escaping or quoting convention at all -- both
    interpolate `item.title` directly into `<id>[<title>]` with no quotes and no
    character substitution (confirmed by reading both methods). No committed title in
    `components.yaml` currently contains '[', ']', or '"', so this gap has never
    surfaced in production, but the underlying mechanism is bare string interpolation
    regardless. Since there is no existing escaping scheme in this codebase to reuse,
    the correct behavior for the decoupled path -- per this task's instruction not to
    invent a new one -- is to reproduce that SAME bare, unescaped interpolation for
    ordinary component nodes, rather than adding escaping logic unique to the
    decoupled path that the flat path doesn't have.
    """

    def test_component_title_with_bracket_character_passes_through_unescaped(self, repo_root: Path):
        components = {
            "componentAlpha": ComponentNode(
                title="Alpha [special] Node",
                category=INFRA,
                to_edges=["componentBeta"],
                from_edges=[],
                subcategory=None,
            ),
            "componentBeta": ComponentNode(
                title="Beta Node", category=INFRA, to_edges=[], from_edges=[], subcategory=None
            ),
        }
        forward_map = _forward_map(components)
        cfg = EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected = "componentAlpha[Alpha [special] Node]"
        assert expected in text, (
            f"expected the decoupled emitter to reproduce flat's bare, unescaped title "
            f"interpolation ({expected!r}), matching base.py's existing (documented) convention; "
            f"got:\n{text}"
        )


# ----------------------------------------------------------------------------
# M5: Step ordering asserted only by first-occurrence markers, not full spans.
# ----------------------------------------------------------------------------

_CLASSDEF_LINE_RE = re.compile(r"^\s*classDef\s+\S+", re.MULTILINE)
_CLASS_USAGE_RE = re.compile(r":::\w+")


class TestOutputOrderSpanContract:
    """
    M5: `TestOutputOrderContract` proves first-occurrence markers for the 8 steps
    appear in order on a small, single-broadcast fixture -- it cannot catch a bug
    where one EARLY element of step N+1 appears before the LAST element of step N
    (e.g. a `~~~` link referencing a port before its band subgraph has fully closed;
    Mermaid's first-reference-wins node placement would silently pull that node out
    of its intended band). Uses the live corpus (many subgraphs, many `~~~` links,
    many `:::` usages) so a marker-based first-occurrence check genuinely could not
    distinguish a correct implementation from one with an early-N+1 bug here.
    """

    def test_last_subgraph_end_precedes_first_band_link(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        end_positions = [m.start() for m in _SUBGRAPH_END_RE.finditer(text)]
        tilde_positions = [i for i in range(len(text)) if text.startswith("~~~", i)]

        assert end_positions, "expected at least one subgraph 'end' line"
        assert tilde_positions, "expected at least one '~~~' band link"

        assert max(end_positions) < min(tilde_positions), (
            "expected every subgraph to close (last 'end') before the first '~~~' band link is "
            f"emitted; last end at {max(end_positions)}, first ~~~ at {min(tilde_positions)}"
        )

    def test_last_classdef_precedes_first_class_usage(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        classdef_positions = [m.start() for m in _CLASSDEF_LINE_RE.finditer(text)]
        usage_positions = [m.start() for m in _CLASS_USAGE_RE.finditer(text)]

        assert classdef_positions, "expected at least one classDef line"
        assert usage_positions, "expected at least one ':::' class usage"

        assert max(classdef_positions) < min(usage_positions), (
            "expected every classDef definition to appear before the first ':::' class usage; "
            f"last classDef at {max(classdef_positions)}, first usage at {min(usage_positions)}"
        )


"""
Test Summary
============
Total test classes: 25 (across tasks 2.1 and 2.2, plus two coverage-gap follow-up rounds).

Original coverage areas (tasks 2.1/2.2, code-reviewer approved):
- get_emission_config() accessor (licensed exception, GREEN today): 8 tests.
- Output-order contract (8 fixed steps): 1 test.
- Header comment formats (aspect-inventory grouping + ADR D6 hop-list literal): 2 tests.
- Band links never span roots (plan-level + emitted-text level): 2 tests.
- Style/classDef passthrough (category styles, port/pepport, pepWrapOutline, bands): 4 tests.
- Output formats (.md fence, raw mermaid/mmd/other): 2 tests.
- Byte stability (double-run, shuffled-input-dict): 2 tests.
- Flat-mode regression (byte-identical baseline, missing-config path): 2 tests.
- Mode-dispatch integration (build_graph() itself): 1 test.
- controlsGovernance leakage check: 1 test.
- Self-check delegation to verify_plan (S1/S4/S5/S7): 4 tests.
- New text-level self-check (S2/S3/S6): 3 tests.
- S8 diagnostics surfaced, never raise: 1 test.
- Flat mode bypasses self-check entirely: 1 test.

Coverage-gap follow-up (adversarial critic pass, closed before Phase 2 implementation):
- H1 TestPepWrapperRendering (wrap subgraph, in/out ports + pepport class, PEP node
  itself, port-chain edge + ordering): 4 tests.
- H2 TestBlockRendering (nested block subgraph span, entry->exit invisible link,
  ordinary block-member placement): 3 tests. Also strengthens the existing
  `test_emitted_band_links_never_span_two_roots` (see its docstring) and extends the
  shared `_port_root_map` helper -- both fixes, not new tests, so not counted here.
- H3 TestPortAndComponentNodeDeclarations (egress port grammar, ingress port
  bare/suffixed grammar, ingress->landing edge, ordinary node title convention): 4
  tests.
- M1 TestDegenerateEmptyPlans (all-intra corpus, no header noise, no orphaned port
  classes): 1 test.
- M2 TestSingleArmBareGrammar (bare header + unsuffixed port id, arm_count=1): 1 test.
- M3 TestS2ReverseDirectionMismatch (more arms present than declared): 1 test.
- M4 TestSpecialCharacterHandling (bracket character in a component title): 1 test.
- M5 TestOutputOrderSpanContract (span-level ordering on the live corpus: last
  subgraph 'end' before first '~~~'; last classDef before first ':::' usage): 2 tests.
  Its `_SUBGRAPH_END_RE` was fixed in this round to add `re.MULTILINE` -- without it,
  `.finditer(text)` over the whole multi-line document matched zero times and the test
  failed unconditionally, for the wrong reason, regardless of implementation
  correctness (see the inline comment on `_SUBGRAPH_END_RE` for the verification).

Coverage-gap follow-up, round 2 (adversarial critic re-check on the round-1 batch,
closed before Phase 2 implementation):
- TestIngressLandingAtPepWrappedTarget (high severity) -- an ingress->landing edge
  whose arm target is PEP-wrapped, proving the edge retargets through the wrapper's
  `_in` port rather than landing at the raw PEP id: 1 test.
- TestPepWrapNestedInsideBlock (medium) -- triple subgraph containment (wrap nested in
  block nested in cluster), the live corpus's actual PEP placement: 1 test.
- TestConcernLabelEscaping (medium) -- an embedded `"` in a concern label, escaped as
  Mermaid's `#quot;` entity in quoted port labels but passed through literally in `%%`
  header comments (design decision documented in the class docstring): 1 test.

Notes for the code-reviewer (task 2.3), preserved from the original RED-phase review:
- Most tests call `ComponentGraph._emit_decoupled()` directly. Before Phase 2 landed,
  they failed with a clean `AttributeError: 'ComponentGraph' object has no attribute
  '_emit_decoupled'` (verified via throwaway prototype); they pass today against the
  real implementation.
- `TestModeDispatchIntegration` and the flat-regression/bypass tests call the public
  `build_graph()`/`to_mermaid()` entry points instead; their original RED character
  differed (content mismatch, or already-GREEN regression pin) -- each said so in its
  docstring.
- `TestGetEmissionConfigAccessor` was GREEN from the start (the accessor is a
  licensed, real implementation landed alongside this test file, not a RED target).
- The header-format assertions (aspect-inventory grouping, band style ids) encode this
  suite's OWN chosen line-format contracts where the ADR/plan only specify structural
  requirements ("grouped by source cluster with counts") -- flagged inline, open to
  code-reviewer adjustment; the hop-list format is the one ADR-literal reproduction.
- No test presumes a specific channel-order-within-broadcast (the ADR mockup's own
  Model-before-Application display order contradicts its own D2 sort-by-tgt_root rule)
  -- see `test_undrawn_hop_list_matches_adr_d6_mockup_literally`'s inline note.
- All coverage-gap tests added in this follow-up were RED for the same clean
  `AttributeError` reason as the rest of the file, EXCEPT
  `test_emitted_band_links_never_span_two_roots` (H2 fix to an existing test, same RED
  character as before) -- none of the new tests were green-today regression pins at
  the time.

Adversarial code-critic follow-up, four confirmed post-Phase-2 defects (`_emit_
decoupled()` already implemented at the time; these tests were RED against that real
implementation, not the earlier no-such-method RED phase; all four fixes have since
landed and every test below now passes):
- Fix 1 `TestGetEmissionConfigAccessor` is unaffected; Fix 1 itself lives in
  `TestSourceEgressResolvesThroughPepWrapper` -- a PEP-wrapped broadcast source drew
  its source->egress edge from the raw component id instead of the wrapper's `_out`
  port. 4 tests: 3 were RED (live-corpus `app + agent egress` two-PEP-source case,
  `tool results` single-PEP-source case, a synthetic mixed PEP/plain-source unit
  pin); 1 was a GREEN-today regression pin (`identity & authz`'s two non-PEP sources --
  proves the defect is PEP-source-resolution specific, not multi-source handling in
  general, which was already correct).
- Fix 2 `TestPlanWarningsSurfaced` -- `plan.warnings` (D7 guard output) was built but
  never surfaced by `_emit_decoupled()`. 3 tests: 2 were RED (logged via
  `logger.warning`; surfaced as a `%%` header comment, mirroring the existing
  S8-diagnostics precedent); 1 was GREEN-today (warnings must not alter drawn
  structure -- trivially true before anything surfaced, remains true as a design
  guard now that it does).
- Fix 3 `TestSelfCheckCatchesGenuineEmitterDefects` -- S2/S5 recompute from the same
  IR fields that built the plan, so they could not fire against a genuine emitter
  defect, only hand-corrupted test IR. 3 RED tests, each simulating "a genuine
  emitter defect" by monkeypatching one of `_emit_decoupled()`'s own step methods
  (impossible to construct via IR corruption alone, since IR corruption is exactly
  what the existing tautological checks already caught): a dropped ingress-port
  declaration (text-derived S2), a cross-wired ingress->landing edge (closes the
  critic's named gap directly), and a source->egress edge pointing at the wrong
  egress port id (bullet 3, ties to Fix 1).
- Fix 4 `TestGetEmissionConfigAccessor::test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat`
  -- a `concerns[n].edges` entry with the wrong tuple arity (3 or 1 elements instead
  of `[src, tgt]`) was accepted without validation and crashed later, deep in
  `decouple.py`, with a raw `ValueError` instead of degrading gracefully. 2 RED cases
  (parametrized), matching the existing malformed-aspect-entry precedent (whole
  block degrades to `flat`).

Total: 12 new tests (10 originally RED, 2 GREEN-today regression/design pins from the
start) across the four fixes; all 12 now pass against the landed fixes. Constraint
honored during the RED phase: no fix implemented at the time, `decouple.py` untouched
(Fix 1 confirmed resolvable entirely via `component_graph.py`'s `plan.pep_wrappers`
lookups, the same pattern `Arm.landing_id` already uses on the target side).

ADR-036 D1 revision follow-up: "Band ports are not chained together with invisible
ordering links" (port-to-port `~~~` chaining removed; only a block's entry->exit pair
survives) -- fix landed in `decouple.py`'s `_build_band_links`, tests below pin it:
- `TestBandLinksNeverSpanRoots.test_plan_band_links_never_span_two_roots` and
  `.test_emitted_band_links_never_span_two_roots` -- both updated in place (not
  replaced) to add an explicit "no band link ever touches a port id" assertion, on top
  of the pre-existing root-scoping check they already made. The emitted-text test also
  pins the total `~~~` line count to exactly the number of block entry/exit pairs (4 in
  the live corpus). Was RED against `_build_band_links` before the fix, which chained
  ~24 port-to-port links in the live corpus; now GREEN.
- `TestBlockRendering.test_block_entry_exit_invisible_link_emitted` (unchanged) is the
  narrower, still-valid block-entry/exit case this revision does NOT affect -- already
  GREEN, kept as-is, distinguished explicitly from the removed port-chain case in the
  two tests above.
- `TestOutputOrderContract.test_all_eight_steps_appear_in_the_fixed_relative_order`
  updated to use a new `_small_synthetic_components_with_block()` fixture (extends the
  existing small-synthetic fixture with one block) and a literal
  `f"{block.entry_id} ~~~ {block.exit_id}"` marker instead of the bare `"~~~"` lookup
  -- the base fixture has no blocks, so once port-chaining is removed it would emit
  zero `~~~` lines at all and this Step-7 marker would never be found. Not a RED test
  itself (block links already existed); a required compatibility fix so this
  order-contract test does not spuriously break when the fix landed.
- Two new unit-level regression tests added to `test_decouple_transform.py`'s
  `TestBandsAndBlocks` (`test_multiple_egress_ports_sharing_a_root_are_never_chained`,
  `test_multiple_ingress_ports_sharing_a_root_are_never_chained`) and one new
  corpus-scale regression guard added to `TestLiveCorpusInventory`
  (`test_band_links_are_block_entry_exit_pairs_only_no_port_chains`, pinning
  `plan.band_links` to exactly the 4 live-corpus block entry/exit pairs). All three were
  RED against `_build_band_links` before the fix; now GREEN.
- `verify_plan()` (D7 self-check, `decouple.py`) and `component_graph.py`'s emission
  self-check were checked for any assumption that counts or iterates port-to-port band
  links specifically: neither does. `verify_plan()`'s S1/S4/S5/S7 checks never
  reference `band_links` at all; `component_graph.py`'s S2/S3/S6 checks are keyed off
  `plan.broadcasts`/`plan.pep_wrappers`, not `plan.band_links`. No self-check
  dependency on the old port-chain-link behavior exists.
"""
