#!/usr/bin/env python3
"""
Tests for the decoupled component-graph emission pass (ADR-036 D1-D9).

`ComponentGraph._emit_decoupled()` -- the private method that serializes a
`DecoupledPlan` (built by `graphing/decouple.py`) into Mermaid text -- is
implemented in `component_graph.py`. `build_graph()`'s mode dispatch
(`config_loader.get_emission_config().mode == "decoupled"` -> `build_decoupled_plan()`
-> `self._emit_decoupled(plan)`) is implemented in the same file. This
suite pins that implementation as a regression guard.

Contract under test (fixed by this suite; the implementation was derived from it):

    ComponentGraph._emit_decoupled(self, plan: DecoupledPlan) -> str
        Serializes the IR in the fixed 8-step output order:
        (1) frontmatter + `graph LR` preamble, (2) header comments (lifted-aspect
        inventory grouped by source cluster, then the undrawn hop list per broadcast),
        (3) `classDef port`/`classDef pepport`, (4) clusters -> bands/blocks/PEP wrap
        subgraphs/nodes, (5) drawn intra edges (wrap -> retarget -> collapse) + PEP
        port chains, (6) source->egress and ingress->landing edges, (7) invisible
        `~~~` band links (never spanning two roots), (8) `style` lines (category
        styles verbatim, band `fill:none,stroke:none`, `pepWrapOutline`). Runs the D7
        emission self-check before returning (delegates to `verify_plan()` for
        S1/S4/S5/S7; adds text-level checks for S2/S3/S6; surfaces `plan.
        diagnostics` for S8 without ever raising on them).

    ComponentGraph.build_graph() dispatches on `self.config_loader.
    get_emission_config().mode`: "flat" (or a missing/corrupt config) takes the
    existing code path verbatim; "decoupled" calls `build_decoupled_plan()` then
    `self._emit_decoupled(plan)`.

`MermaidConfigLoader.get_emission_config()` accessor
=====================================================
`MermaidConfigLoader.get_emission_config()`
(`graphing/graph_utils.py`): `ComponentGraph.__init__`'s signature stays
unchanged (no new constructor parameter), so the emission config has to come
from the loader. It is a MINIMAL, functional accessor -- mode, aspects,
concerns, port_styles -- defaulting to `EmissionConfig(mode="flat")` on any
absent or malformed `graphTypes.component.emission` block (D3: "missing or
corrupt config never yields a half-decoupled diagram"). This accessor's own
contract does not perform schema validation -- that responsibility stays
with check-jsonschema at the YAML-validation layer (see
`get_emission_config()`'s own docstring in `graph_utils.py`).

`risk-map/yaml/mermaid-styles.yaml` carries the real, populated
`graphTypes.component.emission` registry. Tests in
this file that exercise the *decoupled* path construct their own
`EmissionConfig` directly as a fixture (`_live_emission_config()` below), a
reduced fixture that differs in two entries from the shipped registry
`TestLiveCorpusInventory` (`test_decouple_transform.py`) parses directly from
`mermaid-styles.yaml` -- kept as a separate hand-set fixture here rather than
imported, per that suite's own precedent
(`test_decouple_coverage_gaps.py`'s module docstring makes the same call,
for the same reason: independence between test files covering different
concerns). `emission.portStyles` also carries real content in
`mermaid-styles.yaml`; tests needing port styling still use
`PLACEHOLDER_PORT_STYLES` below (documented inline) since they construct
their `EmissionConfig` fixtures directly rather than reading the live
config.

Most tests below call `ComponentGraph._emit_decoupled()` directly, exercising the
method as implemented. A small, explicitly flagged subset of tests instead exercise
`build_graph()`'s mode-dispatch integration directly, proving the dispatch itself
(not just the emitter method) routes to the decoupled path.

Why message-matching, not import-patching, for "delegates to verify_plan"
===========================================================================
The self-check must prove it calls the *existing* `verify_plan()` for
S1/S4/S5/S7 rather than reimplementing equivalent logic. A `mock.patch` on
`decouple.verify_plan` would only intercept the call if `component_graph.py` references
it as `decouple.verify_plan(...)` (module-qualified) -- if it instead does `from
.decouple import verify_plan` (the repo's established import convention; see
`component_graph.py`'s existing `from .graph_utils import MermaidConfigLoader`, `base.
py`'s `from .graph_utils import ...`), the patch would silently miss the locally-bound
name and the test would give a false negative. Rather than bake in an assumption about
which import form the implementation uses, the self-check tests below construct
corrupted-IR fixtures that isolate exactly one of S1/S4/S5/S7 and assert that
`_emit_decoupled()` raises an `AssertionError`
whose message matches `verify_plan`'s own wording, quoted directly from `decouple.py`.
A reimplementation producing a different message fails this match; one that happens to
reproduce `verify_plan`'s exact wording independently is, for all practical purposes,
indistinguishable from delegation and equally acceptable.

Test coverage
=============
Emitter:
 1. `TestGetEmissionConfigAccessor` -- the accessor itself.
 2. `TestOutputOrderContract` -- all 8 steps appear in the correct relative order.
 3. `TestHeaderCommentFormats` -- lifted-aspect inventory grouping (this suite's own
    line-format contract, derived from the plan object, not hardcoded); undrawn hop
    list (literal ADR D6 mockup reproduction, order-independent -- see inline note on
    why channel order itself is not pinned).
 4. `TestBandLinksNeverSpanRoots` -- `plan.band_links` and the emitted `~~~` text never
    span two roots; ADR-036 D1 ("Band ports are not chained together with invisible
    ordering links") additionally requires
    that no band link (IR or emitted) ever chains two port ids together -- only a
    block's entry->exit pair survives.
 5. `TestStyleClassDefPassthrough` -- category styles verbatim; port/pepport classDefs;
    pepWrapOutline; band `fill:none,stroke:none`.
 6. `TestOutputFormats` -- `.md` fence and raw (`mermaid`/`mmd`/anything-else) formats.
 7. `TestByteStability` -- double-run and shuffled-input-dict determinism.
 8. `TestFlatModeRegression` -- byte-identical to the frozen flat-rollback fixture's
    expected output (a regression pin, independent of the live file's mode).
 9. `TestModeDispatchIntegration` -- `build_graph()`'s own mode dispatch.
10. `TestControlsGovernanceLeakage` -- `_create_subgraph_section`'s `controlsGovernance`
    special case is never invoked by the decoupled path.

Self-check:
11. `TestSelfCheckDelegatesToVerifyPlan` -- S1/S4/S5/S7 corrupted-IR fixtures, raise
    propagates with `verify_plan`'s own message.
12. `TestSelfCheckTextLevelChecks` -- S2/S3/S6 new checks raise on violation.
13. `TestSelfCheckDiagnosticsNeverRaise` -- S8: `plan.diagnostics` surfaced, never raises.
14. `TestFlatModeBypassesSelfCheck` -- flat mode never enters the decoupled self-check
    path at all (black-box proof via a real S7-violating registry).

Additional coverage (see the module-end "Test Summary" docstring for the full
gap-to-test mapping):
15. `TestPepWrapperRendering` -- wrap subgraph declaration, in/out ports +
    `:::pepport`, the PEP node itself, and the port-chain edge, positionally checked.
16. `TestBlockRendering` -- nested block subgraph span, entry->exit `~~~` link.
    `TestBandLinksNeverSpanRoots.
    test_emitted_band_links_never_span_two_roots` also asserts block-level `~~~`
    links (see that test's docstring); `_port_root_map` covers
    block entry/exit ids as well as broadcast ports.
17. `TestPortAndComponentNodeDeclarations` -- egress/ingress port node grammar
    (bare and suffixed), ingress->landing edge, ordinary node title convention, all
    positionally checked against their containing band/cluster subgraph span.
18. `TestDegenerateEmptyPlans` -- an all-intra, zero-broadcast, zero-aspect plan
    emits without raising, with no header noise and no orphaned port classDef usage.
19. `TestSingleArmBareGrammar` -- the bare (unsuffixed) single-arm port-id and
    header-line grammar, the counterpart to the existing ⇢3 multi-arm test.
20. `TestS2ReverseDirectionMismatch` -- S2 in the opposite direction (more arms
    present than declared), proving exact-equality rather than a one-sided compare.
21. `TestSpecialCharacterHandling` -- a bracket character in a component title
    passes through exactly as the flat emitter's existing (unescaped) convention does.
22. `TestOutputOrderSpanContract` -- span-level (not just first-occurrence)
    ordering: every subgraph closes before any `~~~` link; every classDef precedes any
    `:::` usage.

Further coverage (see the module-end "Test Summary" docstring for the
full mapping):
23. `TestIngressLandingAtPepWrappedTarget` -- ingress->landing edge composed
    with a PEP-wrapped arm target, proving the edge retargets through the wrapper's
    `_in` port instead of landing at the raw PEP id.
24. `TestPepWrapNestedInsideBlock` -- triple subgraph containment (PEP wrap
    nested inside a block nested inside a cluster), the live corpus's actual shape.
25. `TestConcernLabelEscaping` -- an embedded `"` in a concern label, a
    distinct escaping surface from `TestSpecialCharacterHandling` (quoted
    port-label grammar vs. its unquoted title grammar); design decision documented
    in the class's own docstring.
`TestBlockRendering` also asserts an ordinary block
member (not entry, not exit) is declared inside the block's span.

Emitter coverage (see the
module-end "Test Summary" docstring for the full mapping):
26. `TestSourceEgressResolvesThroughPepWrapper` -- a PEP-wrapped broadcast
    source must exit via its wrapper's `_out` port, not the raw component id.
27. `TestPlanWarningsSurfaced` -- `plan.warnings` (D7 guard output) must be
    surfaced (logged and header-commented), never silently dropped.
28. `TestSelfCheckCatchesGenuineEmitterDefects` -- S2 counts port declarations
    present in the built text; a per-arm landing-edge text assertion (S9) and a
    source->egress destination assertion (S10) catch a cross-wired edge that
    otherwise passes S1-S8.
29. `TestGetEmissionConfigAccessor::test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat`
    -- a malformed edge-tuple arity in `emission.concerns` must degrade to
    flat, not crash later with a raw `ValueError`.

Coverage of S9/S10 themselves (the checks' own implementation, not
the emitted output; see `docs/adr/036-decoupled-component-graph-emission.md` for
background):
30. `TestSelfChecksCatchS9S10ImplementationGaps` -- S9 (and S10's first loop)'s
    `expected in text` match is anchored so that this corpus's prefix-related ids
    (`componentApplication` is a prefix of
    `componentApplicationInputHandling`) do not let a cross-wired edge to the wrong
    (but prefix-related) node pass the check unnoticed. S10's reverse loop flags a
    matched `<src> --> p_out_...` line whether or not its port is a known egress
    port id, so an edge to a nonexistent/typo'd port is flagged rather than
    silently skipped, matching the check's own docstring.

ADR-036 D3/D4 ("Aspect visual marker"): the lifted audit-record sink must be
visually distinguishable in the rendered SVG, not marked only by the invisible
`.mermaid` source comment. A lifted aspect node carries the
`aspectStyle` class and a second label line stating its live lifted in-edge count.
31. `TestAspectVisualMarker` -- the aspect marker's node-declaration grammar
    (synthetic fixture, controlled count), the live corpus
    (`componentAuditRecordRepository`, 17 lifted edges), the count genuinely
    tracking `len(LiftedAspect.edges)` per
    fixture (two fixtures, same aspect id, different counts) rather than a fixed
    string, `classDef aspectStyle` presence, and the zero-lifted-aspects degenerate
    case mirroring `TestDegenerateEmptyPlans` (no orphaned `:::aspectStyle` usage).

Additional coverage (gaps in `TestAspectVisualMarker`/
`TestPortStylesAspectStyleKey`):
32. `TestAspectVisualMarker.
    test_two_simultaneously_lifted_aspects_each_carry_their_own_independent_count`
    -- TWO distinct aspects lift in the SAME plan/emission with different
    counts (3, 5); every other test in the class lifts only
    one aspect at a time, so a positional-lookup bug (`lifted_aspects[0]` instead
    of matching by `aspect_id`) would otherwise pass unnoticed.
33. `TestAspectVisualMarker.
    test_aspect_lifted_but_aspectstyle_not_configured_falls_back_to_plain_node`
    -- pins the "lifted aspect, unconfigured
    `aspectStyle`" contract: gate the entire marker (class + count line) on
    `aspectStyle` being configured; degrade to the ordinary unmarked node
    otherwise. Design decision documented in the class docstring.

ADR-036 D8 (display-layer acronym substitution -- node titles; the
`decouple.py` arm-label counterpart is covered in test_decouple_transform.py):
34. `TestD8PepWrapTitleSubstitutionLiveCorpus` -- live corpus: all 4 real PEP
    titles substitute at both `_decoupled_pep_wrap_lines()` positions, each
    keeping its own prefix; plus a global "phrase never survives" guard.
35. `TestD8PdpTitleGuardLiveCorpus` -- the real, non-PEP-wrapped
    `componentAuthorizationPolicyDecisionPoint` renders unchanged (PDP is
    explicitly out of the D8 set).
36. `TestD8AcronymSubstitutionCaseInsensitivityAndScope` -- synthetic fixtures:
    arbitrary-case matching, ordinary (non-PEP-id) node substitution, PDP/PEP
    side by side in one document.
37. `TestD8SelfCheckAndDeterminismUnaffected` -- full live-corpus emission still
    passes every D7 self-check and stays byte-stable
    (D8-specific regression trip-wire).
38. `TestD8AspectMarkerTitleSubstitution` -- the aspect-marker branch of
    `_decoupled_member_lines()` interpolates a PEP-phrase title correctly (no other
    test combines aspect-lift with a PEP-phrase title).

ADR-036 D9 (consult-class channel landing, emitted-text half):
39. `TestD9ConsultLandingLiveCorpusEmittedText` -- consult-class arms land on the
    bare component id, not the wrapper's `_in` port, in the emitted text;
    data-class arms landing on a wrapped PEP keep `_in`.

40. `TestShippedBlockRendersAgainstTheLiveCorpus` -- renders the shipped
    `graphTypes.component.emission` registry (not a test-owned fixture) through the
    real transform + emission pipeline and checks the output's concern labels and
    aspect marker.
"""

import dataclasses
import logging
import random
import re
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

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
    verify_plan,
)
from riskmap_validator.graphing.graph_utils import _parse_emission_config  # noqa: E402
from riskmap_validator.models import ComponentNode  # noqa: E402
from riskmap_validator.utils import parse_components_yaml  # noqa: E402

# ============================================================================
# Shared helpers (duplicated from test_decouple_transform.py / test_decouple_coverage_gaps.py
# per their own established convention -- independence between test files)
# ============================================================================

INFRA = "componentsInfrastructure"
MODEL = "componentsModel"
APP = "componentsApplication"
TOOLS = "componentsExternalTools"


def _node(category: str, to_edges: list[str] | None = None, subcategory: str | None = None) -> ComponentNode:
    return ComponentNode(
        title="Test Node", category=category, to_edges=to_edges or [], from_edges=[], subcategory=subcategory
    )


def _titled_node(
    category: str, title: str, to_edges: list[str] | None = None, subcategory: str | None = None
) -> ComponentNode:
    """
    `_node()` with a caller-controlled title. `_node()` always uses the fixed "Test
    Node" title, which is unusable for the D8 acronym-substitution tests (they need
    specific title text, e.g. one containing "Policy Enforcement Point" in a
    controlled casing).
    """
    return ComponentNode(
        title=title, category=category, to_edges=to_edges or [], from_edges=[], subcategory=subcategory
    )


def _forward_map(components: dict[str, ComponentNode]) -> dict[str, list[str]]:
    return {cid: node.to_edges[:] for cid, node in components.items()}


def _styles_path(repo_root: Path) -> Path:
    return repo_root / "risk-map" / "yaml" / "mermaid-styles.yaml"


def _live_corpus(repo_root: Path) -> tuple[dict[str, ComponentNode], dict[str, list[str]]]:
    components = parse_components_yaml(repo_root / "risk-map" / "yaml" / "components.yaml").components
    return components, _forward_map(components)


# Frozen flat-rollback corpus pair: a committed copy of the corpus inputs the flat
# emitter needs (components.yaml, plus two mermaid-styles.yaml variants -- one with
# emission.mode explicit 'flat', one with the emission block absent entirely) and the
# expected flat-mode output rendered from them. TestFlatModeRegression reads these
# fixture files directly rather than the live risk-map/ corpus, so a components.yaml
# content edit can never touch this pair, and the pair proves the flat rollback path
# independent of whatever mode graphTypes.component.emission.mode currently declares.
# A genuine flat-emitter rendering change (not a corpus or emission-mode change) is the
# only legitimate reason to refresh the expected output; do so with:
#   PYTHONPATH=./scripts/hooks python3 -c "
#   from pathlib import Path
#   from riskmap_validator.graphing import ComponentGraph, MermaidConfigLoader
#   from riskmap_validator.utils import parse_components_yaml
#   d = Path('scripts/hooks/tests/fixtures/graphing/flat-rollback')
#   components = parse_components_yaml(d / 'components.yaml').components
#   forward_map = {cid: n.to_edges[:] for cid, n in components.items()}
#   loader = MermaidConfigLoader(d / 'mermaid-styles-flat-mode.yaml')
#   graph = ComponentGraph(forward_map, components, config_loader=loader)
#   (d / 'risk-map-graph.mermaid').write_text(graph.to_mermaid(output_format='mermaid'))
#   "
_FLAT_ROLLBACK_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "graphing" / "flat-rollback"


def _read_flat_baseline() -> str:
    return (_FLAT_ROLLBACK_FIXTURE_DIR / "risk-map-graph.mermaid").read_text(encoding="utf-8")


def _flat_rollback_corpus() -> tuple[dict[str, ComponentNode], dict[str, list[str]]]:
    components = parse_components_yaml(_FLAT_ROLLBACK_FIXTURE_DIR / "components.yaml").components
    return components, _forward_map(components)


# Placeholder port styles: tests in this file construct their `EmissionConfig`
# fixtures directly rather than reading the live file's portStyles content, so
# they carry their own copy here. The "port" value is copied verbatim from the
# ADR D6 mockup's `classDef port fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,
# stroke-dasharray:4 3`; pepport/pepWrapOutline are this suite's own placeholder
# strings.
PLACEHOLDER_PORT_STYLES = {
    "port": "fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,stroke-dasharray:4 3",
    "pepport": "fill:#eef7ff,stroke:#2c3e83,stroke-width:1.5px,stroke-dasharray:4 3",
    "pepWrapOutline": "fill:none,stroke:#2c3e83,stroke-width:2px,stroke-dasharray:2 2",
}


def _live_emission_config() -> EmissionConfig:
    """
    The re-derived, live-corpus registry (12 concerns + 1 aspect), reproduced from
    the shipped registry in `risk-map/yaml/mermaid-styles.yaml` (which
    `TestLiveCorpusInventory` in `test_decouple_transform.py` reads directly through
    the production parser, rather than a hand fixture -- see that class's docstring),
    with `port_styles=PLACEHOLDER_PORT_STYLES` added on top -- the transform itself
    (`graphing/decouple.py`) never needed port styling; this file's
    style-passthrough tests do.

    Two entries differ from the shipped registry on purpose, kept
    minimal here rather than fully re-synced, since this fixture is shared by dozens
    of call sites elsewhere in this file that assert specific arm/source sets under
    a reduced registry: `identity & authz` omits the two
    `componentFederationProxy` source edges --
    adding them would not change any arm (both targets are already covered by other
    sources) but would change the broadcast's *source* set, which
    `TestSourceEgressResolvesThroughPepWrapper.
    test_identity_authz_broadcast_multiple_non_pep_sources_each_get_own_edge` pins to
    exactly two; and `model publish` omits the `componentModelTrainingTuning ->
    componentModelStorage` edge for the same reason (it would add a second arm to a
    broadcast other tests do not expect). Both omitted edges remain real, uncovered
    cross edges in the live corpus under this reduced registry and fall back to a
    synthesized label (G-C3) -- harmless here since no test in this file asserts a
    total broadcast/channel/arm count against this shared fixture (that full-registry
    pin lives only in `TestLiveCorpusInventory`, which does not share this fixture).
    """
    return EmissionConfig(
        mode="decoupled",
        aspects=(AspectDecl(id="componentAuditRecordRepository", min_cross_in_degree=10),),
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
                label="endpoint enumeration",
                edges=(("componentToolRegistry", "componentAgentNetworkPolicyEnforcementPoint"),),
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
    the live-corpus registry (or a synthetic one) without depending on what
    `mermaid-styles.yaml`'s own `emission` block currently contains. Instantiated
    directly per `test_mermaid_config_loader.py` convention, never touching the
    production `MermaidConfigLoader.get_instance()` singleton.
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

    Covers block entry/exit ids as well as broadcast ports (see
    `TestBandLinksNeverSpanRoots`'s docstring): a lookup that covered only
    broadcast ports would return `None` for a block entry/exit id, and every
    caller guarding on `is not None` would silently skip exactly the
    block-level `~~~` links -- the one category of band link this helper
    would then be blind to. Block entry/exit ids are unambiguous (each belongs
    to exactly one cluster), so covering them cannot introduce a collision
    with the broadcast-port mapping.
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
# Mermaid subgraph span helper: finds the (start, end) character span of
# a `subgraph <id> ... end` block, tracking nesting depth so a subgraph containing
# further nested subgraphs is not mistaken for closing at its first inner 'end'. Used
# by the tests below to assert that a node/port declaration is POSITIONED
# inside the correct container's text span, not merely present anywhere in the
# document.
# ============================================================================

_SUBGRAPH_OPEN_RE = re.compile(r"^\s*subgraph\s+(\S+)")
# re.MULTILINE is required here: `_subgraph_span` only ever calls `.match(line)` on a
# single line at a time (where `^`/`$` behave the same with or without the flag), but
# `TestOutputOrderSpanContract.test_last_subgraph_end_precedes_first_band_link`
# calls `.finditer(text)` on the WHOLE multi-line document. Without re.MULTILINE, `^`
# and `$` only anchor to the start/end of the entire string, so `finditer` over a
# realistic multi-line emission matches zero times -- the test would fail
# unconditionally (a bogus "expected at least one subgraph 'end' line" error),
# regardless of whether the emitted text is correct.
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
    and S7 clean too. Each override below trips exactly the intended
    `verify_plan()` check and no other.
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
    quoted in the ADR), plus one aspect-lift edge (ModelServing -> AuditSink, a
    genuine cross edge since Model != Infra), one drawn intra edge (Alpha -> Beta), one
    collapsible mirror pair (ModelServing <--> TheModel), and one PEP-touching pair
    (Application -> Gateway PEP -> ReasoningCore) exercising the wrap/retarget path and
    the PEP port chain -- enough surface to exercise all 8 emission steps in one fixture.

    `componentAuditSink` is a synthetic placeholder id, distinct from the live
    corpus's real aspect candidate (`componentAuditRecordRepository`), following the
    synthetic-fixture naming convention `componentAspectSink` uses elsewhere in this
    file: fixtures name their own placeholder ids rather than reusing a real corpus id.
    """
    return {
        "componentRuntimeHosting": _node(
            INFRA, to_edges=["componentModelServing", "componentApplication", "componentReasoningCore"]
        ),
        "componentAlpha": _node(INFRA, to_edges=["componentBeta"]),
        "componentBeta": _node(INFRA, to_edges=[]),
        "componentAuditSink": _node(INFRA, to_edges=[]),
        "componentModelServing": _node(MODEL, to_edges=["componentTheModel", "componentAuditSink"]),
        "componentTheModel": _node(MODEL, to_edges=["componentModelServing"]),
        "componentApplication": _node(APP, to_edges=["componentGatewayPolicyEnforcementPoint"]),
        "componentReasoningCore": _node(APP, to_edges=[]),
        "componentGatewayPolicyEnforcementPoint": _node(APP, to_edges=["componentReasoningCore"]),
    }


def _small_synthetic_cfg() -> EmissionConfig:
    return EmissionConfig(
        mode="decoupled",
        aspects=(AspectDecl(id="componentAuditSink", min_cross_in_degree=1),),
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
    Block-rendering fixture: a single Application cluster containing one subcategory block with an
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

    ADR-036 D1 forbids port-to-port `~~~` chaining
    entirely, and `_small_synthetic_components()` alone has no subcategory blocks --
    so that base fixture emits ZERO `~~~` band links at all. A block's
    entry->exit pair is the only kind of band link D1 permits, so
    `TestOutputOrderContract`'s Step 7 marker needs a block present to have anything
    to find. Used only by that one test; every other test in this suite that calls
    `_small_synthetic_components()` directly is unaffected by this fixture's existence.
    """
    components = dict(_small_synthetic_components())
    components.update(_block_fixture_components())
    return components


def _pep_landing_fixture_components() -> dict[str, ComponentNode]:
    """
    A
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
    Block-with-nested-PEP-wrap fixture: combines
    `_block_fixture_components`'s entry -> middle -> exit block shape with a
    PEP-wrapped middle member, matching the live corpus's actual shape -- all 4 real
    PEPs live inside a subcategory block (see `test_decouple_transform.py`'s
    `TestLiveCorpusInventory`). No existing test nests a PEP wrap subgraph inside a
    block subgraph; `TestPepWrapperRendering` and `TestBlockRendering` each
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
    Degenerate-plan fixture: an all-intra corpus -- one drawn intra edge in
    Infrastructure, one isolated Model node, zero cross edges anywhere. With no
    `emission.aspects` and no `emission.concerns` declared either,
    `build_decoupled_plan` produces zero lifted aspects and zero broadcasts: the
    degenerate case the emitter must still handle without raising and without
    printing empty-section noise.
    """
    return {
        "componentAlpha": _node(INFRA, to_edges=["componentBeta"]),
        "componentBeta": _node(INFRA, to_edges=[]),
        "componentGamma": _node(MODEL, to_edges=[]),
    }


def _degenerate_cfg() -> EmissionConfig:
    return EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)


# ADR-036 D3/D4: `PLACEHOLDER_PORT_STYLES` plus the
# `aspectStyle` key -- kept as a SEPARATE dict rather than adding the key onto
# `PLACEHOLDER_PORT_STYLES` itself, since `TestStyleClassDefPassthrough` and
# `_live_emission_config()` (below) depend on that dict's exact 3-key content;
# a 4th key there would be silently absorbed by every test using `in text`
# containment checks, masking a missing-key regression.
PLACEHOLDER_PORT_STYLES_WITH_ASPECT = {
    **PLACEHOLDER_PORT_STYLES,
    "aspectStyle": "fill:#fdf6e3,stroke:#b58900,stroke-width:1.5px,stroke-dasharray:4 3",
}


def _live_emission_config_with_aspect_style() -> EmissionConfig:
    """`_live_emission_config()` plus `port_styles=PLACEHOLDER_PORT_STYLES_WITH_ASPECT`.

    A separate helper rather than a mutation of `_live_emission_config()` itself,
    for the same isolation reason as `PLACEHOLDER_PORT_STYLES_WITH_ASPECT` above.
    """
    return dataclasses.replace(_live_emission_config(), port_styles=PLACEHOLDER_PORT_STYLES_WITH_ASPECT)


def _aspect_marker_components(source_count: int) -> dict[str, ComponentNode]:
    """
    Aspect-marker fixture: a single INFRA sink (`componentAspectSink`, out-degree 0,
    subcategory=None so the D4 block-orphan guard never triggers) with exactly
    `source_count` cross in-edges from MODEL/APP sources, and no other edges --
    isolates the aspect marker's live-derived count from every other transform
    concern (single lifted aspect, zero broadcasts, zero intra edges). Title is
    fixed ("Test Node" via `_node()`), so the marker's first label line is
    identical across every `source_count` value, keeping the count the ONLY
    thing that varies between two calls with different `source_count`.
    """
    components: dict[str, ComponentNode] = {"componentAspectSink": _node(INFRA, to_edges=[])}
    for i in range(source_count):
        category = MODEL if i % 2 == 0 else APP
        components[f"componentAspectSrc{i}"] = _node(category, to_edges=["componentAspectSink"])
    return components


def _aspect_marker_cfg(source_count: int) -> EmissionConfig:
    """`minCrossInDegree` set exactly to `source_count` -- the D4 guard is `<`, so equality qualifies."""
    return EmissionConfig(
        mode="decoupled",
        aspects=(AspectDecl(id="componentAspectSink", min_cross_in_degree=source_count),),
        port_styles=PLACEHOLDER_PORT_STYLES_WITH_ASPECT,
    )


def _two_aspect_marker_components() -> dict[str, ComponentNode]:
    """
    Two-simultaneously-lifted-aspects fixture: TWO distinct INFRA sinks
    (`componentAspectSinkX`/`componentAspectSinkY`, both out-degree 0,
    subcategory=None) with DIFFERENT, fixed lifted-edge counts -- X gets 3 cross
    in-edges, Y gets 5 -- from MODEL/APP sources, mirroring
    `_aspect_marker_components()`'s single-sink shape but doubled, so both nodes
    coexist in the SAME plan/emission. Distinct sink ids (not a repeated call to
    `_aspect_marker_components()`, which always uses the single id
    `componentAspectSink`) are required for two lifted aspects to appear together
    at all.
    """
    components: dict[str, ComponentNode] = {
        "componentAspectSinkX": _node(INFRA, to_edges=[]),
        "componentAspectSinkY": _node(INFRA, to_edges=[]),
    }
    for i in range(3):
        category = MODEL if i % 2 == 0 else APP
        components[f"componentAspectSrcX{i}"] = _node(category, to_edges=["componentAspectSinkX"])
    for i in range(5):
        category = MODEL if i % 2 == 0 else APP
        components[f"componentAspectSrcY{i}"] = _node(category, to_edges=["componentAspectSinkY"])
    return components


def _two_aspect_marker_cfg() -> EmissionConfig:
    """Both `componentAspectSinkX` (3 sources) and `componentAspectSinkY` (5 sources) qualify to lift."""
    return EmissionConfig(
        mode="decoupled",
        aspects=(
            AspectDecl(id="componentAspectSinkX", min_cross_in_degree=3),
            AspectDecl(id="componentAspectSinkY", min_cross_in_degree=5),
        ),
        port_styles=PLACEHOLDER_PORT_STYLES_WITH_ASPECT,
    )


# ============================================================================
# 1. get_emission_config() accessor
# ============================================================================


class TestGetEmissionConfigAccessor:
    """
    See the module docstring's accessor section for
    `MermaidConfigLoader.get_emission_config()`'s contract. These tests exercise the
    accessor directly, independent of the emitter itself.
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
            "        - id: componentAuditSink\n"
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
        assert cfg.aspects == (AspectDecl(id="componentAuditSink", min_cross_in_degree=10),)
        assert cfg.concerns == (
            ConcernDecl(label="runtime hosting", edges=(("componentRuntimeHosting", "componentModelServing"),)),
        )
        assert cfg.port_styles == {"port": "fill:#fff"}

    def test_malformed_aspect_entry_missing_required_key_defaults_to_flat(self, tmp_path):
        config_file = tmp_path / "mermaid-styles.yaml"
        config_file.write_text(
            "version: '1.0.0'\nfoundation: {}\nsharedElements: {}\n"
            "graphTypes:\n  component:\n    emission:\n      mode: decoupled\n"
            "      aspects:\n        - id: componentAuditSink\n",  # missing minCrossInDegree
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
        A `concerns[n].edges` entry whose tuple arity is not exactly 2 (`[src, tgt]`)
        is rejected by `_validated_edge()`, which raises `ValueError` on any shape
        that is not a 2-element list/tuple. `get_emission_config()`'s
        `except (KeyError, TypeError, ValueError)` catches that and degrades the
        whole `emission` block to `flat`, matching this accessor's own docstring
        promise ("missing or corrupt config never yields a half-decoupled diagram").

        The bare-string case (`edges: [componentA]` written without the inner list,
        i.e. a plain scalar) is included because it is the shape most likely to
        evade validation by a different route: `tuple("componentA")` silently
        succeeds, producing a 14-character tuple rather than raising, so
        `_validated_edge()`'s explicit `isinstance(edge, str)` check -- rather than
        an arity check alone -- is what catches it.

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

    def test_real_committed_config_resolves_to_flat_mode(self, repo_root: Path):
        """
        Pins what `get_emission_config()` returns against the real, committed
        `mermaid-styles.yaml`: `mode` resolves to `"flat"`, the shipped
        production setting -- this is the accessor reading the real file, not
        a synthetic fixture, so it moves in lockstep with the committed
        `emission.mode` value.
        """
        loader = MermaidConfigLoader(_styles_path(repo_root))
        assert loader.get_emission_config().mode == "flat"


# ============================================================================
# 2. Output-order contract (steps 1-8)
# ============================================================================


class TestOutputOrderContract:
    """
    All 8 fixed-order emission steps must appear, in order, in the built Mermaid text.
    Uses the small synthetic fixture (`_small_synthetic_components`/`_small_synthetic_cfg`),
    extended with one block (`_small_synthetic_components_with_block()`) so Step 7 has
    a genuine `~~~` marker to find -- ADR-036 D1 forbids port-to-port chaining, so
    the base fixture alone (no subcategory blocks) emits zero `~~~` lines,
    and only a block's entry->exit pair
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
        # what ADR-036 requires ("the undrawn p_out <-> p_in hop list per broadcast").
        marker_2 = f"{broadcast.label} ⇢ {broadcast.arm_count}"
        # Step 3: classDef port/pepport.
        marker_3 = "classDef port"
        # Step 4: cluster subgraph declarations.
        marker_4 = "subgraph componentsInfrastructure"
        # Step 5: drawn intra edges (the plain Alpha->Beta intra edge).
        marker_5 = "componentAlpha --> componentBeta"
        # Step 6: source->egress edge.
        marker_6 = f"componentRuntimeHosting --> {broadcast.egress_port_id}"
        # Step 7: invisible band link -- ADR-036 D1 forbids port-to-port chaining, so
        # the only kind of `~~~` link is a block's entry->exit pair (the
        # Application-cluster block added by `_small_synthetic_components_with_block()`);
        # this marker is not a bare "~~~" lookup.
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
    Lifted-aspect inventory grouping (this suite's own line-format contract -- ADR-036
    D4 requires a "grouped header-comment inventory", not a literal
    string) and the undrawn hop list (ADR D6's literal mockup, order-independent).
    """

    def test_lifted_aspect_inventory_grouped_by_source_cluster_with_correct_counts(self, repo_root: Path):
        """
        This suite's own header-line contract: one comment line per source cluster
        feeding the lifted aspect, naming its count and (sorted) member source ids --
        derived programmatically from `plan.lifted_aspects` rather than hardcoded, so
        this test doesn't presume a specific literal wording beyond the line SHAPE it
        defines (`%%   <clusterId> (<count>): <sorted comma-separated source ids>`).
        Uses the live corpus (componentAuditRecordRepository, 17 lifted edges across
        3 source clusters) since the small synthetic fixture only has one source
        cluster.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        lifted = plan.lifted_aspects[0]
        assert lifted.aspect_id == "componentAuditRecordRepository"
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
        Model-then-Application ordering. ADR-036 D6 itself says only the "port-id
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

        ADR-036 D1 ("Band ports are not chained together with invisible
        ordering links"): additionally asserts that no band link touches a port id at
        all. A band's own subgraph nesting is what pins its ports to the container's
        edge (ELK's compound-node contiguity constraint); only a block's entry->exit
        pair (one link, two real component nodes) survives. Regression pin against
        `_build_band_links` chaining port-to-port links.
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
                f"band link ({a}, {b}) is a port-to-port chain link; ADR-036 D1 "
                "('band ports are not chained') -- only "
                "block entry/exit pairs are retained"
            )

    def test_emitted_band_links_never_span_two_roots(self, repo_root: Path):
        """
        Exercises the emitted `~~~` text itself, not just the IR.

        `_port_root_map` maps both broadcast ports and block entry/exit ids to
        their cluster root, so every `~~~` endpoint in the live corpus resolves;
        the lookups below are hard assertions, not a guarded skip.

        ADR-036 D1: additionally asserts that no emitted `~~~` line's endpoint
        is a port id, and that the total emitted `~~~` line count equals exactly
        the number of block entry/exit pairs -- zero port-to-port chain lines. A
        chain among a band's ports that stays root-scoped passes the root-span
        check above while still producing the sprawl D1 forbids, so this
        assertion is needed to catch it directly. Regression pin against
        `_build_band_links` emitting any port-to-port `~~~` lines in the live
        corpus, in addition to the 4 block links.
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
                    f"emitted band link in line {line!r} chains a port id; ADR-036 D1 "
                    "forbids port-to-port '~~~' links"
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
# 7. Byte stability (D7: same YAML in -> byte-identical .mermaid out)
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
        Same shuffle technique/seed as `test_decouple_coverage_gaps.py`'s
        `TestShuffledInputDeterminismAtTheTransformLevel` test,
        extended from the IR (the transform's guarantee, already proven there) to the
        built Mermaid TEXT -- that suite's own docstring says text-level equivalence
        is the emission pass's job; this is that job.
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
# 8. Flat-mode regression
# ============================================================================


class TestFlatModeRegression:
    """
    The flat emission path is untouched by the decoupled-mode work and stays pinned
    against the frozen flat-rollback fixture pair (`_FLAT_ROLLBACK_FIXTURE_DIR`) --
    a committed corpus (components.yaml + two mermaid-styles.yaml variants) and its
    expected flat output, read directly rather than through the live risk-map/ files.
    A components.yaml content edit can never touch this pair, and a real flat-emitter
    regression still fails it, independent of whatever mode the live, committed
    `mermaid-styles.yaml` currently declares.
    """

    def test_flat_mode_matches_committed_baseline_exactly(self):
        """
        Given: the frozen corpus fixture and its mermaid-styles.yaml variant with
               emission.mode explicit 'flat'
        When:  the graph is rendered
        Then:  the output is byte-identical to the frozen expected output
        """
        components, forward_map = _flat_rollback_corpus()
        loader = MermaidConfigLoader(_FLAT_ROLLBACK_FIXTURE_DIR / "mermaid-styles-flat-mode.yaml")
        graph = ComponentGraph(forward_map, components, config_loader=loader)
        assert graph.to_mermaid(output_format="mermaid") == _read_flat_baseline()

    def test_missing_emission_config_also_takes_flat_path(self):
        """
        Given: the frozen corpus fixture and its mermaid-styles.yaml variant with
               the `graphTypes.component.emission` block absent entirely
        When:  the get_emission_config() accessor is asked for the mode
        Then:  it degrades to 'flat' by its own absent-block default, and
               build_graph() output matches the frozen expected output exactly
        """
        components, forward_map = _flat_rollback_corpus()
        loader = MermaidConfigLoader(_FLAT_ROLLBACK_FIXTURE_DIR / "mermaid-styles-no-emission-block.yaml")
        assert loader.get_emission_config().mode == "flat"

        graph = ComponentGraph(forward_map, components, config_loader=loader)
        assert graph.to_mermaid(output_format="mermaid") == _read_flat_baseline()


# ============================================================================
# 9. Mode-dispatch integration (build_graph() itself)
# ============================================================================


class TestModeDispatchIntegration:
    """
    Integration test for `build_graph()`'s mode-dispatch contract: `build_graph()`
    reads `config_loader.get_emission_config()`; mode == 'decoupled' calls
    `build_decoupled_plan()` then `self._emit_decoupled(plan)`.

    UNLIKE most tests in this file, this one calls the PUBLIC `build_graph()` entry
    point rather than `_emit_decoupled()` directly, to pin the dispatch integration
    itself, not just the emitter method in isolation.
    """

    def test_decoupled_mode_config_routes_through_emit_decoupled(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        graph = _make_graph(components, forward_map, cfg, repo_root)

        output = graph.build_graph()

        assert "p_out_infra_runtime_hosting" in output
        assert output != _read_flat_baseline()


# ============================================================================
# 10. controlsGovernance leakage check
# ============================================================================


class TestControlsGovernanceLeakage:
    """
    `_create_subgraph_section` in `base.py` is the flat emitter's generic
    subgraph-declaration helper. The decoupled path builds its own
    cluster/band/PEP-wrap subgraph rendering rather than reusing the flat helper
    at all -- confirm it never routes through `_create_subgraph_section`, so any
    category-specific handling added to that flat-path helper can never leak
    into the decoupled emitter.
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
# 12. Text-level checks: S2, S3, S6
# ============================================================================


class TestSelfCheckTextLevelChecks:
    """
    These properties are invisible to `verify_plan()` (an IR-only self-check) --
    the emission pass's own self-check adds them. Each fixture below is
    verified against `verify_plan()` to NOT trip any of its S1/S4/S5/S7 checks,
    isolating exactly the check under test.
    """

    def test_s2_broadcast_arm_count_mismatch_raises(self, repo_root: Path):
        """Declared arm_count (5) doesn't match the actual arms present (1) --
        verify_plan doesn't check this at all (arm_count is a bare int field it never
        cross-references); the S2 check must."""
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
        entirely (the port id isn't a real components dict key), so only the S3
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
        plan has a real PEP wrapper needing them -- a config/plan mismatch the S6
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
# Text-derived self-checks: catching a defect the IR alone cannot reveal
# ============================================================================


class TestSelfCheckCatchesGenuineEmitterDefects:
    """
    S2 (`_check_s2_arm_counts`) counts the actual ingress-port declarations
    present in the BUILT TEXT (`f'{arm.port_id}["'` occurrences) and compares that
    count against `broadcast.arm_count`, falling back to the IR arm count only when
    `plan.clusters` is empty (the isolated self-check unit fixtures elsewhere in this
    file construct a bare IR with no cluster structure, so there is no rendered text
    to count). S9 (`_check_arm_landing_edges`) likewise asserts that every arm's
    `<port_id> --> <landing_id>` edge literally appears in the built text.

    Concretely: a cross-wired ingress->landing edge (an arm's port pointing
    at the wrong node in the rendered text, while the IR's own `arm.landing_id` field
    is correct) would pass every IR-derived check (S1, S3-S8) undetected; S2 and S9
    close that gap by counting and matching against the BUILT TEXT instead of the IR.

    Because `_emit_decoupled()`/`decouple.py` cannot MISWIRE
    their own output (the text is built directly and correctly from the IR every
    time), each test below simulates
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
        Genuine text-derived S2. Simulates an emitter bug that drops one
        arm's ingress PORT NODE DECLARATION from the cluster-subgraph ingress band
        (`_decoupled_cluster_subgraphs`) while its `port_id --> landing_id` edge
        (a separate method, `_decoupled_edges`) is still drawn correctly -- the IR
        itself (`plan.broadcasts[*].channels[*].arms`, `arm_count`) is completely
        untouched and internally consistent. `_check_s2_arm_counts` counts port
        declarations actually present in the built text (`f'{arm.port_id}["'`
        occurrences), so it asserts this test raises: it finds only 2 declared
        ports for a `⇢ 3` broadcast here and raises `AssertionError`.
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
        S9 asserts that every arm's `<port_id> --> <landing_id>` edge literally
        appears in the built text. Simulates an emitter bug that draws one arm's
        ingress edge to the WRONG node (a cross-wired landing) instead of
        `arm.landing_id` -- the arm's declared `landing_id` in the IR is untouched
        and correct, the port's rendered out-degree is still exactly 1 (S3 does not
        fire: it only counts out-degree, never checks WHERE the edge points), and
        no S1-S8 check inspects a specific arm's edge destination at all -- S9 is
        the only check that does.
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
        S10 extends text-level checking to source->egress lines, ties in
        naturally with `_check_source_egress_edges`'s source-resolution logic -- a
        resolution bug there is exactly a source->egress edge pointing at an
        unexpected port id. Simulates an emitter bug that draws the broadcast
        source's egress edge to a bogus, unrelated port id instead of
        `broadcast.egress_port_id`. No S1-S8 check inspects a source->egress line's
        destination -- S10 is the only check that does.
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
    S9 and S10 (`_check_arm_landing_edges`, `_check_source_egress_edges`) match
    against the built text with `_anchored_edge_pattern`, not a bare `expected in
    text` substring check. The tests below pin that behavior against the two ways
    an unanchored check would miss a cross-wired edge:

    Anchored matching (S9 + S10's first loop): since the expected string's tail is
    a component id, and this corpus's real ids have genuine prefix relationships
    (`componentApplication` is a strict prefix of
    `componentApplicationInputHandling`, `componentApplicationOutputHandling`,
    `componentApplicationConsentSurface`, and
    `componentApplicationNetworkPolicyEnforcementPoint`), an unanchored `expected in
    text` substring check would let a cross-wired edge to the WRONG node whose id
    happens to extend the correct one satisfy `expected in text` via prefix match
    against the wrong line. `TestSelfCheckCatchesGenuineEmitterDefects.
    test_arm_port_to_landing_edge_must_literally_appear_in_built_text` above does not
    already cover this: its cross-wired target (`componentApplication`) is NOT a
    prefix of the correct landing id, so it is caught by the "expected line is simply
    absent" case, not this substring-collision case.

    Unfiltered reverse loop (S10's reverse loop flags any mismatched port, not only
    known ones): the reverse sweep flags every found `<src> --> <port>` line that
    is not in `expected_pairs`, regardless of whether `port` belongs to any
    broadcast, so an emitted edge to a port id that doesn't belong to ANY broadcast
    (a typo'd or stale port) is flagged rather than silently passed -- matching the
    check's own docstring ("catches a source wired to the wrong (or a nonexistent)
    broadcast port"). Distinct from the existing
    `test_source_to_egress_edge_pointing_at_wrong_egress_port_is_caught` above, which
    REPLACES the correct line (so the first loop's "expected pair missing" branch
    already catches it); this test ADDS an extra bogus line while leaving every
    correct edge in place, isolating the reverse loop as the only branch that could
    catch it.
    """

    def test_arm_landing_edge_cross_wired_to_a_prefix_related_sibling_id_is_caught(self, repo_root: Path):
        """
        Live corpus: the "runtime hosting" broadcast's arm landing at
        `componentApplication` (`p_in_app_runtime_hosting_application`) is
        cross-wired to `componentApplicationInputHandling` -- a real, live, but wrong
        sibling id that happens to extend `componentApplication` as a substring.
        Under an unanchored `expected in text` check, `"p_in_app_runtime_
        hosting_application --> componentApplication" in text` would still be True
        (it is a substring of the wrong line), so an unanchored S9 would not fire on
        this collision; this test pins S9's anchored match against exactly that case.
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
        Live corpus: an extra, bogus `<src> --> p_out_...` line is appended
        alongside every correct source->egress edge (none removed), pointing at a
        port id that belongs to no broadcast at all. A reverse loop filtered to
        `port in egress_port_ids` would silently skip this line (and the first loop
        never fires, since every expected pair is still present verbatim); this
        test pins S10's unfiltered reverse-loop check against exactly that case.
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
# plan.warnings (D7 guard output) must be surfaced
# ============================================================================


class TestPlanWarningsSurfaced:
    """
    `plan.warnings` (the D7 guard
    output, G-A1..G-O1) must be surfaced by `_emit_decoupled()`, not dropped --
    a guard warning (e.g. a stale aspect id, or a threshold violation) must be
    logged and commented, never silently swallowed.

    Design decision: surface via BOTH channels, mirroring the existing S8
    diagnostics precedent (`TestSelfCheckDiagnosticsNeverRaise`), which already
    surfaces `plan.diagnostics` both via `logger.debug` AND a header comment --
      1. `logger.warning()`, once per warning message -- verified via `caplog`.
      2. A `%%`-prefixed header-comment block (step 2, alongside the lifted-aspect
         inventory and hop lists) -- more discoverable than a log line, since it
         lands directly in the committed `.mermaid` artifact that is this repo's
         actual diagram-review surface.
    Warnings must never raise (that is `validate_riskmap.py --block`'s territory, not
    this emitter's) and must never change the drawn plan/output structure -- pinned
    by the third test below via a diff against the same plan with `warnings=[]`.
    """

    def _threshold_violation_fixture(self):
        """
        Reuses `test_decouple_guards.py::TestGA3AspectBelowThreshold`'s exact fixture
        shape (an aspect whose live cross in-degree, 7, is below its configured
        `minCrossInDegree`, 10) -- an existing below-threshold fixture, reused here
        rather than invented fresh.
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
        this exact components/forward_map/concerns combination is the
        slug-collision fixture from `test_decouple_coverage_gaps.py`'s
        `TestSlugCollisionBetweenDistinctConcernLabels`, which makes `verify_plan()`
        raise `S7 violated: port id collision(s): [...]` when `mode="decoupled"`. Feeding the
        SAME registry through `mode="flat"` must not raise -- if it did, the decoupled
        self-check (or `build_decoupled_plan`) ran despite `mode="flat"`, violating the
        D3 rollback contract. This is independent of `component_graph.py`'s internal
        import mechanism for `verify_plan`/`build_decoupled_plan` (see module docstring
        "Why message-matching, not import-patching").

        Calls the PUBLIC `build_graph()` (not `_emit_decoupled()`), since this test is
        about the MODE DISPATCH itself: it is a regression pin for the D3 rollback
        contract.
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
# Additional emitter coverage: PEP wrap rendering, block rendering, port/node
# declaration grammar, degenerate plans, single-arm grammar, S2 mismatch in the
# reverse direction, special characters, and span-level output ordering. Each
# test below exercises `_emit_decoupled()` directly unless its docstring says
# otherwise.
# ============================================================================


# ----------------------------------------------------------------------------
# PEP wrapper rendering: wrap subgraph, ports, PEP node placement, port-chain edge.
# ----------------------------------------------------------------------------


class TestPepWrapperRendering:
    """
    The synthetic fixture (`_small_synthetic_components`/`_small_synthetic_cfg`)
    already includes a PEP-matching component (`componentGatewayPolicyEnforcementPoint`)
    specifically to exercise the wrap/retarget path. `TestIngressLandingAtPepWrappedTarget`,
    `TestSourceEgressResolvesThroughPepWrapper`, and `TestPepWrapNestedInsideBlock` below
    cover PEP-related output too, from other angles (retargeted landing, source
    resolution, block containment); this class covers the wrapper's own rendering.
    `plan.pep_wrappers[...]` is the authoritative source for the
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
        Step 5 emits the PEP port chain literally: `pep_in --> pep --> pep_out`
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
# Block (subcategory) rendering: nested subgraph span, entry->exit link, members.
# ----------------------------------------------------------------------------


class TestBlockRendering:
    """
    Uses `_block_fixture_components`/`_block_fixture_cfg` (an Application cluster with
    one subcategory block, entry -> middle -> exit) to pin block-subgraph nesting
    within its cluster, the entry->exit invisible link, and ordinary block-member
    placement inside the block's span. `TestPepWrapNestedInsideBlock` below combines
    this same block shape with a nested PEP wrap.
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
        # Sanity: `_build_band_links` already computes this pair into the IR.
        assert (block.entry_id, block.exit_id) in plan.band_links

        expected_link = f"{block.entry_id} ~~~ {block.exit_id}"
        assert expected_link in text, (
            f"expected block entry->exit invisible link {expected_link!r} in emitted text"
        )

    def test_ordinary_block_member_declared_inside_block_span(self, repo_root: Path):
        """
        The two tests above prove the block subgraph itself is declared and
        nested, and that the entry->exit `~~~` link exists -- but neither ever
        asserts that an ORDINARY block member (not the
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

        # Flat title convention (see TestSpecialCharacterHandling/
        # TestPortAndComponentNodeDeclarations): `<id>[<title>]`, unquoted.
        expected = f"{middle_id}[Test Node]"
        assert expected in text, f"expected ordinary block member node {expected!r} in emitted text"
        pos = text.index(expected)
        assert block_start < pos < block_end, "ordinary block member must be declared inside its block's span"


# ----------------------------------------------------------------------------
# Port and component node declarations: egress/ingress port grammar, node titles.
# ----------------------------------------------------------------------------


class TestPortAndComponentNodeDeclarations:
    """
    Uses `_small_synthetic_components`/`_small_synthetic_cfg` (the D6 worked
    "runtime hosting" example: a bare Model arm, two suffixed Application arms).
    Literal grammar re-derived from ADR-036 D6's mockup:
        egress:  `<id>["▸ <label>  ⇢ <n>"]:::port`   (note the two spaces before ⇢)
        ingress: `<id>["<arm.label> ▸"]:::port`
    and from `base.py`'s existing `_create_subgraph_section`/`_get_nested_subgraph_new`
    convention for ordinary node titles: `<id>[<title>]` -- NO surrounding quotes (both
    methods interpolate `item.title` bare).
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
# Composition coverage: PEP-wrapped arm landing composed with the PEP-wrap
# rendering it draws through, PEP-wrap-inside-block nesting, block-member
# placement, and concern-label escaping. Each test below pins
# `_emit_decoupled()`'s handling of that composition, unless its docstring
# says otherwise.
# ----------------------------------------------------------------------------


class TestIngressLandingAtPepWrappedTarget:
    """
    `TestPortAndComponentNodeDeclarations.
    test_ingress_to_landing_edge_emitted_for_at_least_one_arm` reads
    `plan.broadcasts[0].channels[0].arms[0]` from `_small_synthetic_cfg()`'s "runtime
    hosting" broadcast, whose first (alphabetically sorted) arm target --
    `componentReasoningCore` -- is a plain component, not PEP-wrapped. PEP-wrapping
    (`TestPepWrapperRendering`) and arm-landing (`TestPortAndComponentNodeDeclarations`,
    this class's sibling) are each
    tested, but never TOGETHER: an emitter that drew `arm.port_id --> arm.target` (the
    raw PEP component id) instead of the correct `arm.port_id --> arm.landing_id` (the
    wrapper's `_in` port, per `decouple.py::_build_arms`'s `landing_id =
    pep_wrappers[target].in_id if target in pep_wrappers and not is_consult else
    target`) would pass both of those classes while producing wrong edges for every
    live-corpus data-class arm that lands at a PEP's `_in` port -- `tool calls` and
    both `inference / serving` arms (the consult-class arms, `identity & authz` and
    `endpoint enumeration`, land on the component id instead, per ADR-036 D9; see
    `mermaid-styles.yaml`'s `emission.concerns` registry). Uses a
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
        assert arm.landing_id == wrapper.in_id  # sanity: the transform's own retargeting rule (already proven)

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
    The sibling to `TestIngressLandingAtPepWrappedTarget` above, but on the
    SOURCE side of a broadcast: `_decoupled_edges`'s source->egress line construction
    (`component_graph.py`) resolves a PEP-wrapped source through `plan.pep_wrappers
    [src].out_id`, so the cross-boundary edge is drawn from the wrapper's `_out` port,
    never the bare PEP node id -- matching ADR-036 D3's rationale for PEP wrappers
    ("a reader sees traffic entering and leaving through the enforcement point").
    Pinned below against the live corpus: the two `app + agent egress`
    sources and the `tool results` source.

    This resolution lives entirely in the emission layer via
    `plan.pep_wrappers` lookups (`Arm.landing_id` uses the identical
    pattern on the target side in `decouple.py::_build_arms`); these tests exercise
    `_emit_decoupled()` only, never `decouple.py` directly.
    """

    def test_app_agent_egress_broadcast_both_pep_sources_resolve_through_out_port(self, repo_root: Path):
        """
        Live corpus: the `app + agent egress` broadcast has
        TWO distinct sources, both PEP-wrapped (`componentAgentNetworkPolicy
        EnforcementPoint`, `componentApplicationNetworkPolicyEnforcementPoint`).
        Asserts a source->egress edge per DISTINCT source (see the
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

        # Literal, hardcoded reproduction of the expected output, independent of the
        # programmatically-derived strings above.
        assert "agentNetworkPep_out --> p_out_app_app_agent_egress" in text
        assert "applicationNetworkPep_out --> p_out_app_app_agent_egress" in text
        assert "componentAgentNetworkPolicyEnforcementPoint --> p_out_app_app_agent_egress" not in text
        assert "componentApplicationNetworkPolicyEnforcementPoint --> p_out_app_app_agent_egress" not in text

    def test_tool_results_broadcast_single_pep_source_resolves_through_out_port(self, repo_root: Path):
        """Live corpus: the `tool results` broadcast's sole source is the
        tool-network PEP -- the third live-corpus PEP-wrapped-source instance."""
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
        Live corpus: the `identity & authz` broadcast has multiple distinct
        sources, none of which is PEP-wrapped, asserting a source->egress edge
        per source. `_decoupled_edges` draws a non-PEP-wrapped source's edge from
        the raw component id and iterates the full distinct-source set, so this
        pins that behavior as a regression guard, distinct from
        `TestSourceEgressResolvesThroughPepWrapper`'s PEP-source-resolution path
        above, which is not exercised by non-PEP sources.

        The expected source set is DERIVED from `cfg`'s own `identity & authz`
        concern edges (filtered to non-PEP sources), not a hardcoded pair. This
        fixture (`_live_emission_config()`) is deliberately a reduced view of
        the shipped registry (its docstring: two `componentFederationProxy`
        source edges omitted, on purpose, for call-site stability elsewhere in
        this file) -- a hardcoded two-element list would silently pass and
        silently stay wrong if that reduction is ever narrowed back toward the
        shipped registry's three non-PEP sources. Deriving from `cfg` itself
        makes the assertion track whatever this specific fixture actually
        declares.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        identity_concern = next(c for c in cfg.concerns if c.label == "identity & authz")
        expected_sources = sorted({src for src, _tgt in identity_concern.edges})

        broadcast = next(b for b in plan.broadcasts if b.label == "identity & authz")
        sources = sorted({src for channel in broadcast.channels for src, _tgt in channel.edges})
        assert sources == expected_sources
        for source in sources:
            assert source not in plan.pep_wrappers  # sanity: none of the declared sources is PEP-wrapped

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
        raw id), proving the resolution is a per-source lookup, not a broadcast-wide switch.
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
    `TestPepWrapperRendering` proves a PEP wrap subgraph is declared and
    `TestBlockRendering` proves a block subgraph is nested inside its cluster --
    but no existing test nests a PEP wrap subgraph INSIDE a block
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
    Distinct from `TestSpecialCharacterHandling`'s title-escaping test -- concern
    labels flow into a DIFFERENT Mermaid grammar than component titles. Component
    titles interpolate bare and UNQUOTED (`<id>[<title>]`, confirmed by reading
    `base.py` directly) inside a bracket-delimited node shape. Concern labels
    interpolate into QUOTED port-label strings
    (`<id>["<label> ▸"]:::port`, `<id>["▸ <label>  ⇢ <n>"]:::port` -- see
    `TestPortAndComponentNodeDeclarations`/`TestSingleArmBareGrammar`) and into
    `%%`-prefixed header comment lines (see `TestHeaderCommentFormats`).

    Neither the ADR (D3's "concern labels are semantic knowledge about edges living in
    a styling file" framing) nor `decouple.py`'s `slug()` docstring say anything about
    escaping. This test therefore makes its
    own explicit design-decision call rather than leaving the behavior ambiguous:

    1. Quoted port-label text (the grammar delimited by literal `"..."`) is the one
       surface where an embedded `"` character is not merely cosmetically odd (the
       bracket case `TestSpecialCharacterHandling` pins, which stays syntactically
       valid Mermaid even unescaped, since brackets inside an already-quoted string
       need no delimiter protection) but SYNTAX-BREAKING: an unescaped `"`
       prematurely closes the quoted string, garbling every token after it on that
       line. Passing it through bare, the way `TestSpecialCharacterHandling` pins
       for component titles, would not merely look ugly here -- it would emit
       genuinely invalid Mermaid, which is exactly what ADR-036 D7's stated
       philosophy exists to prevent ("a generator that
       silently emits a wrong diagram is worse than one that raises"). This test
       therefore expects the emitter to escape an embedded `"` using Mermaid's own
       documented mechanism for this exact situation -- the `#quot;` HTML-entity
       code for quoted flowchart labels -- rather than inventing a bespoke escaping
       scheme unique to this codebase (`#quot;` is Mermaid's own convention, not a
       new one).
    2. `%%`-prefixed header comment lines are a different grammar: a Mermaid line
       comment runs verbatim to end-of-line and is never string-delimited, so a `"`
       character there is inert -- it does not need escaping to remain valid Mermaid.
       This test therefore expects the header-comment occurrence of the SAME label to
       pass through literally (unescaped), matching the same "no invented escaping"
       precedent `TestSpecialCharacterHandling` pins for titles, for the one grammar
       context here where raw passthrough is genuinely safe.
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
        # Bare single-arm form (see TestSingleArmBareGrammar): the transform passes
        # the label through as-is, quote character and all -- escaping is strictly
        # the emission pass's concern.
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
# Degenerate/empty plans.
# ----------------------------------------------------------------------------


class TestDegenerateEmptyPlans:
    """
    A plan with zero lifted aspects and zero broadcasts/channels (an all-intra
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
# ADR-036 D3/D4: aspect visual marker.
# ----------------------------------------------------------------------------


class TestAspectVisualMarker:
    """
    A lifted aspect node carries the `aspectStyle` class and a second label line
    stating its live lifted in-edge count (ADR-036 D3/D4). Implemented in
    `_decoupled_member_lines()` in `component_graph.py`. Without that marker,
    every member (including a lifted aspect) would be declared with the same
    plain `<id>[<title>]` line as an ordinary node. This suite pins the marker
    as a regression guard.

    Grammar choice: this suite pins Mermaid's own standard
    flowchart line-break token, `<br/>`, as the separator between the title line
    and the count line -- the same token Mermaid's own documentation and the
    wider flowchart ecosystem use for a multi-line node label, and, unlike a
    literal `\\n`, one that does not require switching the node's `[...]` grammar
    from unquoted to quoted. The marker therefore reuses the EXISTING unquoted
    `<id>[<title>]` grammar `TestPortAndComponentNodeDeclarations.
    test_ordinary_component_node_declared_with_flat_title_convention` already
    pins for ordinary nodes, with two additions layered on top: the `<br/>`
    line break plus the count line, and the `:::aspectStyle` class suffix -- the
    same `:::<className>` suffix grammar `:::port`/`:::pepport` already use
    (`TestPortAndComponentNodeDeclarations`, `TestPepWrapperRendering`).

    Count-line wording (`"N writes lifted"`) is quoted directly from ADR-036 D4's
    own illustrative text ("e.g. '17 writes lifted'"), pinned here as the exact,
    generic (non-aspect-specific) wording -- ADR-036 declares no per-aspect label
    template and the corpus has exactly one aspect candidate today
    (`componentAuditRecordRepository`), so "writes lifted" is treated as this ADR's
    fixed phrasing rather than something derived from the current aspect's specific
    semantics.

    Two-simultaneous-lift coverage: every test above lifts exactly
    ONE aspect. D4 admits a second sink by config edit, and none of the above would catch a
    `_decoupled_member_lines()` bug that looked up `plan.lifted_aspects[0]` by
    position instead of matching `member_id` against `LiftedAspect.aspect_id` --
    such a bug would mislabel every aspect node after the first with the wrong
    count, yet pass every test above (each has only one lifted aspect, so
    `[0]` and "the matching entry" are indistinguishable). See
    `test_two_simultaneously_lifted_aspects_each_carry_their_own_independent_count`
    below, which lifts two aspects with different counts (3 and 5) in the same
    plan and asserts each node carries only its own count.

    Design decision: what happens when a lifted aspect exists but
    `emission.portStyles` has no `aspectStyle` key at all (e.g. the 3-key
    `PLACEHOLDER_PORT_STYLES` fixture used throughout this file's other
    tests)? Two
    divergent implementations both pass every OTHER test in this class: (a) emit
    `:::aspectStyle` usage unconditionally, even with no matching `classDef`
    (silently unstyled in a real render), or (b) gate the ENTIRE marker -- both
    the class suffix and the "N writes lifted" second label line -- on
    `aspectStyle` actually being configured, falling back to the plain, unmarked
    `id[title]` node -- the same form an ordinary, non-aspect component uses.

    DECISION: (b). This matches the established `port`/`pepport` precedent
    already in this codebase -- `_decoupled_classdefs`'s own docstring says those
    classDefs are "emitted whenever the config supplies the corresponding
    style", and the `TestDegenerateEmptyPlans` guard above already forbids an
    orphaned `:::port`/`:::pepport` class USAGE when the config doesn't back it.
    Option (a) would create exactly that same orphaned-class-usage shape for
    `aspectStyle`, just triggered by config absence rather than plan absence --
    the same failure mode under a different cause, which this repo's
    config-driven-features-degrade-gracefully convention (see also
    `TestFlatModeRegression`'s missing-config-never-half-decoupled precedent)
    rules out. `plan.lifted_aspects` membership and the D4 exclusion from drawn
    edges are UNAFFECTED by this decision -- an aspect with unconfigured styling
    is still correctly lifted and still correctly absent from
    `_decoupled_edges`; only its rendered PRESENTATION degrades to an ordinary
    node. See
    `test_aspect_lifted_but_aspectstyle_not_configured_falls_back_to_plain_node`
    below.

    S6 self-check consequence of this decision: S6 (`_check_s6_style_classdef_
    presence`) must NOT gain a clause requiring `aspectStyle`'s presence merely
    because an aspect was lifted -- doing so would contradict graceful
    degradation by turning a config omission that this class's decision treats
    as a legitimate (if plainer) rendering into a hard emission failure. This is
    consistent with (not a change to) the existing S6 contract: S6 already
    requires `classDef port`/`classDef pepport` only when the PLAN actually
    draws a port/PEP wrapper that needs them (`_check_s6_style_classdef_
    presence`'s own docstring: "only when the plan actually draws ports/PEP
    wrappers"), never merely because a style COULD have been used; `aspectStyle`
    follows the identical shape, one level further -- absence degrades the
    OUTPUT instead of raising, so S6 has nothing to check either way.
    `test_s6_missing_pepport_classdef_raises` does not exercise `aspectStyle`
    at all.
    """

    def test_synthetic_fixture_known_count_declares_node_with_class_and_two_line_label(self, repo_root: Path):
        """
        Controlled count (3), NOT the live corpus's real count -- a real check on
        the exact label text, isolated from whatever `componentAuditRecordRepository`'s
        current cross in-degree happens to be.
        """
        components = _aspect_marker_components(3)
        forward_map = _forward_map(components)
        cfg = _aspect_marker_cfg(3)
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert len(plan.lifted_aspects[0].edges) == 3, "sanity: this fixture's controlled lifted-edge count"
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected = "componentAspectSink[Test Node<br/>3 writes lifted]:::aspectStyle"
        assert expected in text, f"expected aspect marker node declaration {expected!r}; got:\n{text}"

    def test_live_corpus_secure_logging_carries_marker_with_the_real_seventeen_count(self, repo_root: Path):
        """
        The live corpus, not a synthetic fixture: `componentAuditRecordRepository`
        is the current sink -- ADR-036 names the sink by role, not by id. It must
        carry the marker with its real, current lifted in-edge count.

        The "17" is independently cross-checked against a direct count of cross
        edges into the sink from the raw corpus (mirroring
        `test_undrawn_hop_list_matches_adr_d6_mockup_literally`'s pattern of
        cross-checking a derived string against a literal one), rather than
        hardcoded, so the assertion tracks the corpus instead of drifting from it.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config_with_aspect_style()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        aspect_id = "componentAuditRecordRepository"
        cross_in_degree = sum(
            1
            for src, targets in forward_map.items()
            for tgt in targets
            if tgt == aspect_id and components[src].category != components[tgt].category
        )
        assert cross_in_degree == 17

        lifted = plan.lifted_aspects[0]
        assert lifted.aspect_id == aspect_id
        assert len(lifted.edges) == cross_in_degree

        text = graph._emit_decoupled(plan)

        title = components[aspect_id].title
        expected_derived = f"{aspect_id}[{title}<br/>{len(lifted.edges)} writes lifted]:::aspectStyle"
        expected_literal = (
            "componentAuditRecordRepository[Audit Record Repository<br/>17 writes lifted]:::aspectStyle"
        )
        assert expected_derived == expected_literal, "sanity: the derived and literal strings must agree"
        assert expected_literal in text, f"expected live-corpus aspect marker {expected_literal!r}; got:\n{text}"

    def test_count_tracks_each_fixtures_own_lifted_edges_not_a_hardcoded_string(self, repo_root: Path):
        """
        Two independent fixtures, the SAME aspect id (`componentAspectSink`), two
        DIFFERENT lifted-edge counts (3 and 5). If the emitted count were a fixed
        string anywhere in the emitter rather than read from `LiftedAspect.edges`
        at emission time, either both fixtures would emit the same count, or one
        would emit the other's -- this test fails either way; it only passes if
        each fixture's own build independently reflects its own actual count.
        """
        for count in (3, 5):
            components = _aspect_marker_components(count)
            forward_map = _forward_map(components)
            cfg = _aspect_marker_cfg(count)
            plan = build_decoupled_plan(forward_map, components, cfg)
            assert len(plan.lifted_aspects[0].edges) == count
            graph = _make_graph(components, forward_map, cfg, repo_root)

            text = graph._emit_decoupled(plan)

            expected = f"componentAspectSink[Test Node<br/>{count} writes lifted]:::aspectStyle"
            assert expected in text, f"expected count={count} reflected in the marker label; got:\n{text}"

            other_count = 5 if count == 3 else 3
            leaked = f"componentAspectSink[Test Node<br/>{other_count} writes lifted]:::aspectStyle"
            assert leaked not in text, (
                f"fixture with count={count} must not also emit the OTHER fixture's count "
                f"({other_count}) -- {leaked!r} unexpectedly present; got:\n{text}"
            )

    def test_classdef_aspectstyle_present_when_a_lifted_aspect_exists(self, repo_root: Path):
        """Mirrors `TestStyleClassDefPassthrough.
        test_port_and_pepport_classdefs_present_with_configured_strings` for the
        `aspectStyle` class."""
        components = _aspect_marker_components(3)
        forward_map = _forward_map(components)
        cfg = _aspect_marker_cfg(3)
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected = f"classDef aspectStyle {PLACEHOLDER_PORT_STYLES_WITH_ASPECT['aspectStyle']}"
        assert expected in text, f"expected {expected!r} in emitted text; got:\n{text}"

    def test_no_orphaned_aspectstyle_usage_when_zero_lifted_aspects(self, repo_root: Path):
        """
        Degenerate-plan guard, extended to `aspectStyle` (mirrors
        `TestDegenerateEmptyPlans.
        test_emission_succeeds_with_no_header_lines_and_no_orphaned_port_classes`
        exactly): `classDef aspectStyle` is config-driven and position-fixed, the
        same as `classDef port`/`classDef pepport` (`_decoupled_classdefs`'s own
        docstring: "emitted whenever the config supplies the corresponding style,
        independent of whether this particular plan uses" it) -- so it is
        expected to still be emitted here even though this plan lifts nothing.
        What must NOT happen, mirroring `TestDegenerateEmptyPlans`'s port/pepport
        assertions,
        is an orphaned `:::aspectStyle` USAGE on any node.
        """
        components = _degenerate_components()
        forward_map = _forward_map(components)
        cfg = EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES_WITH_ASPECT)
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert plan.lifted_aspects == []
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)  # must not raise

        expected_classdef = f"classDef aspectStyle {PLACEHOLDER_PORT_STYLES_WITH_ASPECT['aspectStyle']}"
        assert expected_classdef in text, f"expected {expected_classdef!r} in emitted text; got:\n{text}"
        assert ":::aspectStyle" not in text, "no node should carry an orphaned :::aspectStyle usage"

    def test_two_simultaneously_lifted_aspects_each_carry_their_own_independent_count(self, repo_root: Path):
        """
        The emission-layer sibling of `test_decouple_transform.py::
        TestAspectCandidacy.
        test_two_aspects_lift_simultaneously_each_with_independent_edge_count` --
        same two-independent-sinks shape, exercised through `_emit_decoupled()`
        instead of the raw IR. Two distinct aspect ids (`componentAspectSinkX`,
        `componentAspectSinkY`) lift in the SAME plan/emission with DIFFERENT
        lifted-edge counts (3 and 5).

        Unlike `test_count_tracks_each_fixtures_own_lifted_edges_not_a_hardcoded_
        string` above (which loops over two SEQUENTIAL, INDEPENDENT plan/emission
        builds, one per count), this test builds ONE plan containing BOTH lifted
        aspects at once. A `_decoupled_member_lines()` bug that read
        `plan.lifted_aspects[0]` by position instead of matching `member_id`
        against `LiftedAspect.aspect_id` would pass the sequential test (each of
        its two builds has exactly one lifted aspect, so `[0]` is always correct
        there) while silently giving sink Y sink X's count (or an
        IndexError/wrong-node mismatch) here -- this is the one test in this class
        where that class of bug is visible.
        """
        components = _two_aspect_marker_components()
        forward_map = _forward_map(components)
        cfg = _two_aspect_marker_cfg()
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert len(plan.lifted_aspects) == 2, "sanity: this fixture's two independent aspects must both lift"
        by_id = {la.aspect_id: la for la in plan.lifted_aspects}
        assert len(by_id["componentAspectSinkX"].edges) == 3, "sanity: sink X's controlled lifted-edge count"
        assert len(by_id["componentAspectSinkY"].edges) == 5, "sanity: sink Y's controlled lifted-edge count"
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected_x = "componentAspectSinkX[Test Node<br/>3 writes lifted]:::aspectStyle"
        expected_y = "componentAspectSinkY[Test Node<br/>5 writes lifted]:::aspectStyle"
        assert expected_x in text, f"expected sink X's own marker {expected_x!r}; got:\n{text}"
        assert expected_y in text, f"expected sink Y's own marker {expected_y!r}; got:\n{text}"

        leaked_x_as_y = "componentAspectSinkY[Test Node<br/>3 writes lifted]:::aspectStyle"
        leaked_y_as_x = "componentAspectSinkX[Test Node<br/>5 writes lifted]:::aspectStyle"
        assert leaked_x_as_y not in text, f"sink Y must not carry sink X's count -- got:\n{text}"
        assert leaked_y_as_x not in text, f"sink X must not carry sink Y's count -- got:\n{text}"

    def test_aspect_lifted_but_aspectstyle_not_configured_falls_back_to_plain_node(self, repo_root: Path):
        """
        See this class's docstring "Design decision" section for the full
        contract writeup. Config carries an aspect
        declaration that genuinely qualifies for lift (`min_cross_in_degree`
        exactly matches the fixture's 3 sources, reusing `_aspect_marker_
        components(3)`/its matching threshold), but `port_styles` is the
        3-key `PLACEHOLDER_PORT_STYLES` fixture -- no `aspectStyle`
        key at all.

        DECISION (pinned here): the marker is gated entirely on `aspectStyle`
        being configured. With it absent, the lifted aspect node falls back to
        the ordinary, unmarked `id[title]` declaration -- no `:::aspectStyle`
        class usage anywhere, no "N writes lifted" label text, no orphaned
        `classDef aspectStyle` line (there is nothing to be orphaned FROM, since
        the config never supplied the style string in the first place). The
        aspect is still genuinely lifted at the IR level (`plan.lifted_aspects`
        still has the entry) -- only its rendered presentation degrades.

        Not a tautological pass: `_decoupled_member_lines()` gates the marker on
        `aspectStyle` being configured, so this exact config (aspectStyle
        unconfigured) produces the plain fallback line by that gate, not by
        coincidence. An implementation that emitted `:::aspectStyle`
        unconditionally (option (a), rejected above) would fail this test --
        the same role `TestFlatModeRegression`'s byte-identical baseline test
        plays for the flat path.
        """
        components = _aspect_marker_components(3)
        forward_map = _forward_map(components)
        # Same aspect declaration as `_aspect_marker_cfg(3)`, but with the
        # 3-key `PLACEHOLDER_PORT_STYLES` (no `aspectStyle`) swapped
        # in for `port_styles` -- isolates "aspectStyle unconfigured" from "aspect
        # not lifted" (the aspect still qualifies; only its styling is missing).
        cfg = dataclasses.replace(_aspect_marker_cfg(3), port_styles=PLACEHOLDER_PORT_STYLES)
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert len(plan.lifted_aspects) == 1, "sanity: the aspect must still lift despite unconfigured styling"
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)  # must not raise

        assert ":::aspectStyle" not in text, "no node should carry an unstyled :::aspectStyle usage"
        assert "writes lifted" not in text, "no count label should appear without aspectStyle configured"
        assert "classDef aspectStyle" not in text, "no classDef line for a style that was never configured"
        expected_plain = "componentAspectSink[Test Node]"
        assert expected_plain in text, (
            f"expected the lifted aspect to fall back to the ordinary, unmarked node "
            f"declaration {expected_plain!r}; got:\n{text}"
        )


# ----------------------------------------------------------------------------
# Single-arm (bare label, unsuffixed port id) text grammar.
# ----------------------------------------------------------------------------


class TestSingleArmBareGrammar:
    """
    The only existing hop-list assertion
    (`test_undrawn_hop_list_matches_adr_d6_mockup_literally`) covers the ⇢3 multi-arm
    case. Uses the live corpus's "tool hosting" broadcast (1 arm) to exercise
    `_build_arms`'s bare-vs-suffixed logic when `multi_arm` is False.
    """

    def test_single_arm_broadcast_uses_bare_header_and_unsuffixed_port_id(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        broadcast = next(b for b in plan.broadcasts if b.label == "tool hosting")
        assert broadcast.arm_count == 1  # sanity: this is the single-arm case (live registry)
        arm = broadcast.channels[0].arms[0]
        assert arm.label == "tool hosting", "bare label -- no '→ <target>' suffix"
        assert arm.port_id == "p_in_tools_tool_hosting", "unsuffixed port id -- no '_<target>' suffix"

        expected_header = f"%% {broadcast.label} ⇢ 1 — the port-to-port hops are documented here, never drawn:"
        assert expected_header in text, f"expected literal bare-form header line {expected_header!r}"

        expected_ingress_node = f'{arm.port_id}["{arm.label} ▸"]:::port'
        assert expected_ingress_node in text, f"expected bare ingress port node {expected_ingress_node!r}"


# ----------------------------------------------------------------------------
# S2 tested elsewhere only in one direction.
# ----------------------------------------------------------------------------


class TestS2ReverseDirectionMismatch:
    """
    The only existing S2 test (`TestSelfCheckTextLevelChecks.
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
# Escaping/special characters.
# ----------------------------------------------------------------------------


class TestSpecialCharacterHandling:
    """
    Pins the decoupled emitter's behavior for a component title containing a
    Mermaid-syntax-sensitive character. Component titles (not concern labels) are the
    realistic surface here: concern labels come from the small, curated
    `emission.concerns` registry (a dozen hand-written entries), while titles are
    freeform content authored per-component in `components.yaml`.

    The existing flat emitter (`base.py::_create_subgraph_section`/
    `_get_nested_subgraph_new`) has NO escaping or quoting convention at all -- both
    interpolate `item.title` directly into `<id>[<title>]` with no quotes and no
    character substitution. No committed title in
    `components.yaml` currently contains '[', ']', or '"', so this gap has never
    surfaced in production, but the underlying mechanism is bare string interpolation
    regardless. Since there is no existing escaping scheme in this codebase to reuse,
    the correct behavior for the decoupled path is to reproduce that SAME bare,
    unescaped interpolation for ordinary component nodes, rather than inventing
    escaping logic unique to the decoupled path that the flat path doesn't have.
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
# Step ordering asserted elsewhere only by first-occurrence markers, not full spans.
# ----------------------------------------------------------------------------

_CLASSDEF_LINE_RE = re.compile(r"^\s*classDef\s+\S+", re.MULTILINE)
_CLASS_USAGE_RE = re.compile(r":::\w+")


class TestOutputOrderSpanContract:
    """
    `TestOutputOrderContract` proves first-occurrence markers for the 8 steps
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


# ----------------------------------------------------------------------------
# ADR-036 D8: display-layer acronym substitution ("policy enforcement point" (case-
# insensitive) -> "PEP", node titles only -- decouple.py's arm-label site is covered
# in test_decouple_transform.py). Implemented in `component_graph.py`
# (`_decoupled_pep_wrap_lines()` calls `apply_display_acronyms()` from `decouple.py`).
# This suite pins the D8 acronym-substitution behavior as a regression guard.
#
# Real corpus facts (risk-map/yaml/components.yaml): exactly 4 components match
# the PEP wrap id suffix, all Title Case:
#   componentAgentNetworkPolicyEnforcementPoint       -> "Agent Network Policy Enforcement Point"
#   componentApplicationNetworkPolicyEnforcementPoint -> "Application Network Policy Enforcement Point"
#   componentToolNetworkPolicyEnforcementPoint        -> "Tool Network Policy Enforcement Point"
#   componentAuthorizationPolicyEnforcementPoint      -> "Authorization Policy Enforcement Point"
# and one real, non-PEP-wrapped component whose title spells out the explicitly-
# held-out PDP counterpart:
#   componentAuthorizationPolicyDecisionPoint -> "Authorization Policy Decision Point"
#
# `_decoupled_pep_wrap_lines()` renders a PEP component's title at TWO positions --
# the wrap subgraph's own header label (`subgraph <wrap_id> ["<title>"]`) and the
# PEP node's own declaration line inside the wrap (`<pep_id>[<title>]`) -- both from
# the same unsubstituted `self.components[wrapper.pep_id].title` read
# (`component_graph.py`'s `_decoupled_pep_wrap_lines`). This site is
# title-bearing (twice over), not just port/chain lines, so both positions
# need the substitution and both are asserted below.
# ----------------------------------------------------------------------------


class TestD8PepWrapTitleSubstitutionLiveCorpus:
    """
    Live-corpus proof that `_decoupled_pep_wrap_lines()` substitutes D8's
    acronym at both title positions (wrap header, PEP node line), and that
    each of the 4 PEPs keeps its own distinguishing prefix -- a single generic
    "PEP" replacement losing "Agent Network"/"Application Network"/"Tool
    Network"/"Authorization" would fail this test.
    """

    def test_live_corpus_pep_titles_verified_before_asserting_substitution(self, repo_root: Path):
        """
        Sanity/documentation: pins today's real, unsubstituted title strings so the
        substituted expectations in the next test are provably derived from the live
        corpus, not guessed.
        """
        components, _forward_map_ = _live_corpus(repo_root)
        assert components["componentAgentNetworkPolicyEnforcementPoint"].title == (
            "Agent Network Policy Enforcement Point"
        )
        assert components["componentApplicationNetworkPolicyEnforcementPoint"].title == (
            "Application Network Policy Enforcement Point"
        )
        assert components["componentToolNetworkPolicyEnforcementPoint"].title == (
            "Tool Network Policy Enforcement Point"
        )
        assert components["componentAuthorizationPolicyEnforcementPoint"].title == (
            "Authorization Policy Enforcement Point"
        )

    def test_all_four_pep_wrap_titles_render_as_pep_each_keeping_its_own_prefix(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected_titles = {
            "componentAgentNetworkPolicyEnforcementPoint": "Agent Network PEP",
            "componentApplicationNetworkPolicyEnforcementPoint": "Application Network PEP",
            "componentToolNetworkPolicyEnforcementPoint": "Tool Network PEP",
            "componentAuthorizationPolicyEnforcementPoint": "Authorization PEP",
        }
        for pep_id, expected_title in expected_titles.items():
            wrapper = plan.pep_wrappers[pep_id]
            wrap_start, wrap_end = _subgraph_span(text, wrapper.wrap_id)
            wrap_text = text[wrap_start:wrap_end]

            expected_header = f'subgraph {wrapper.wrap_id} ["{expected_title}"]'
            expected_node = f"{wrapper.pep_id}[{expected_title}]"
            assert expected_header in text, f"expected wrap header {expected_header!r}; got:\n{text}"
            assert expected_node in wrap_text, (
                f"expected PEP node declaration {expected_node!r} inside its own wrap span; got:\n{wrap_text}"
            )

    def test_spelled_out_phrase_never_survives_anywhere_in_emitted_text(self, repo_root: Path):
        """
        Global regression guard covering both substitution sites (node titles
        here, `_build_arms`'s `arm_label` in `decouple.py`): D8's spelled-out
        phrase must not survive anywhere in the built text -- not merely at the
        two known title positions. Port ids are unaffected by construction
        (slugged with underscores, e.g. '..._policy_enforcement_point', a different
        substring than the spaced phrase asserted against here), so this assertion
        can never collide with the D7 port-id byte-stability invariant.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        assert "policy enforcement point" not in text.lower(), (
            "expected the spelled-out phrase to be fully replaced by 'PEP' (ADR-036 D8); "
            "found a remaining occurrence in the emitted text"
        )


class TestD8PdpTitleGuardLiveCorpus:
    """
    Regression guard, live-corpus form: `componentAuthorizationPolicyDecisionPoint`
    is a real corpus component (id does not match the PEP wrap suffix, so it renders
    through `_decoupled_member_lines()`'s ordinary branch, not the PEP wrap path) whose
    title spells out "Policy Decision Point" -- the exact NIST 800-162/800-207 pairing
    ADR-036 D8 evaluated and explicitly held out. Must render completely unchanged.

    Regression guard confirming D8 leaves the PDP title untouched.
    """

    def test_pdp_component_title_renders_unchanged(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        assert components["componentAuthorizationPolicyDecisionPoint"].title == (
            "Authorization Policy Decision Point"
        )
        # Sanity: this id genuinely does not match the PEP wrap suffix pattern, so it
        # is rendered by _decoupled_member_lines(), not _decoupled_pep_wrap_lines().
        assert "componentAuthorizationPolicyDecisionPoint" not in plan.pep_wrappers

        text = graph._emit_decoupled(plan)

        expected = "componentAuthorizationPolicyDecisionPoint[Authorization Policy Decision Point]"
        assert expected in text, f"expected PDP node title unchanged; got:\n{text}"


class TestD8AcronymSubstitutionCaseInsensitivityAndScope:
    """
    Synthetic, controlled-title fixtures isolating three D8 claims the live corpus
    alone cannot cleanly separate:

    1. Case-insensitive matching for a source casing that is neither the live
       corpus's Title Case nor `target_short_name()`'s all-lowercase -- an
       arbitrary mixed-case title, proving the match is genuinely
       case-insensitive rather than keyed to one specific casing convention.
    2. `_decoupled_member_lines()` (the ordinary, non-PEP-wrap node path) also
       substitutes the phrase in a title -- proving the substitution is a pure
       text overlay, unconditional on the component id matching the PEP wrap
       suffix pattern (`componentLegacyAdapter` below deliberately does not
       match it).
    3. "Policy Decision Point" is untouched at both sites in one fixture,
       side-by-side with a PEP occurrence that IS substituted -- ruling out a
       naive "Policy * Point" pattern that would wrongly catch both.
    4. (Word-boundary anchoring) The PLURAL phrase
       "Policy Enforcement Points" is a different phrase than D8's singular
       match target ("policy enforcement point", case-insensitive) and must
       render byte-for-byte unchanged -- ruling out a naive substring/regex
       match with no trailing word-boundary anchor, which would also match
       inside the plural and wrongly collapse it (to "PEPs", or to "PEP" with
       a dangling "s").
    """

    def _plan_and_graph(
        self, components: dict[str, ComponentNode], repo_root: Path
    ) -> tuple[DecoupledPlan, ComponentGraph]:
        forward_map = _forward_map(components)
        cfg = EmissionConfig(mode="decoupled", port_styles=PLACEHOLDER_PORT_STYLES)
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)
        return plan, graph

    def test_pep_wrap_title_substitutes_case_insensitively_for_arbitrary_mixed_case_source(self, repo_root: Path):
        components = {
            "componentGatewayPolicyEnforcementPoint": _titled_node(APP, "Gateway PoLiCy ENFORCEMENT poInt"),
        }
        plan, graph = self._plan_and_graph(components, repo_root)
        text = graph._emit_decoupled(plan)

        wrapper = plan.pep_wrappers["componentGatewayPolicyEnforcementPoint"]
        wrap_start, wrap_end = _subgraph_span(text, wrapper.wrap_id)
        wrap_text = text[wrap_start:wrap_end]

        assert f'subgraph {wrapper.wrap_id} ["Gateway PEP"]' in text, f"got:\n{text}"
        assert f"{wrapper.pep_id}[Gateway PEP]" in wrap_text, f"got:\n{wrap_text}"

    def test_ordinary_member_title_substitutes_even_when_component_id_is_not_pep_suffixed(self, repo_root: Path):
        components = {
            "componentLegacyAdapter": _titled_node(APP, "Legacy policy enforcement point Relay"),
        }
        plan, graph = self._plan_and_graph(components, repo_root)
        text = graph._emit_decoupled(plan)

        assert "componentLegacyAdapter" not in plan.pep_wrappers  # sanity: not wrap-treated
        assert "componentLegacyAdapter[Legacy PEP Relay]" in text, f"got:\n{text}"

    def test_pdp_title_unchanged_alongside_a_substituted_pep_title_in_the_same_document(self, repo_root: Path):
        components = {
            "componentAuthorizationPolicyDecisionPoint": _titled_node(APP, "Authorization Policy Decision Point"),
            "componentGatewayPolicyEnforcementPoint": _titled_node(APP, "Gateway Policy Enforcement Point"),
        }
        plan, graph = self._plan_and_graph(components, repo_root)
        text = graph._emit_decoupled(plan)

        assert "componentAuthorizationPolicyDecisionPoint[Authorization Policy Decision Point]" in text, (
            f"PDP title must render unchanged; got:\n{text}"
        )
        wrapper = plan.pep_wrappers["componentGatewayPolicyEnforcementPoint"]
        assert f"{wrapper.pep_id}[Gateway PEP]" in text, f"got:\n{text}"

    def test_plural_policy_enforcement_points_phrase_is_left_completely_unchanged(self, repo_root: Path):
        """
        D8's rule (word-boundary anchoring): a
        phrase match on the SINGULAR "policy enforcement point" only. A naive
        substring/regex implementation with no trailing word-boundary anchor would
        also match inside the plural "Policy Enforcement Points" -- wrongly
        collapsing it to "PEPs", or to "PEP" with a dangling "s" left over. Neither
        is D8's rule: the plural is a different phrase and must render completely
        unchanged.

        Paired with a singular occurrence in a SECOND component's title, in the
        SAME plan/assertion pass -- mirrors `TestD8PdpArmLabelNeverAbbreviated`'s
        side-by-side PDP+PEP pattern in test_decouple_transform.py: the singular
        case genuinely substitutes per D8, proving this fixture would catch a
        naive implementation that failed to substitute anything at all, while the
        plural, right next to it, stays untouched, ruling out a
        non-word-boundary-anchored match that would wrongly catch the plural too.
        """
        components = {
            "componentGatewayCore": _titled_node(APP, "Gateway Policy Enforcement Point"),
            "componentGatewayCluster": _titled_node(APP, "Gateway Policy Enforcement Points"),
        }
        plan, graph = self._plan_and_graph(components, repo_root)
        text = graph._emit_decoupled(plan)

        # Singular: substituted per D8.
        assert "componentGatewayCore[Gateway PEP]" in text, f"got:\n{text}"
        # Plural: unchanged, per D8's word-boundary anchoring.
        assert "componentGatewayCluster[Gateway Policy Enforcement Points]" in text, (
            f"expected the plural phrase to render completely unchanged; got:\n{text}"
        )
        assert "componentGatewayCluster[Gateway PEPs]" not in text, (
            f"expected no incorrect 'PEPs' collapse of the plural phrase; got:\n{text}"
        )
        assert "componentGatewayCluster[Gateway PEP]" not in text, (
            f"expected no incorrect singular 'PEP' collapse with a dangling 's'; got:\n{text}"
        )


class TestD8SelfCheckAndDeterminismUnaffected:
    """
    ADR-036 D8's own body text recommends "a D7-style self-check
    assertion (a port id is byte-identical with the substitution applied or not)
    ... tracked in Follow-up rather than mandated here." The Follow-up confirms that
    runtime check is not built with this PR; a regression test,
    `TestD8ArmLabelSubstitutionLiveCorpus::
    test_pep_landing_arm_port_ids_are_byte_identical_to_todays_captured_values`
    in `test_decouple_transform.py`, pins the live corpus's port ids instead. This
    class pins the broader claim implied by D8's recommendation: the FULL
    live-corpus decoupled emission still passes every D7 self-check
    (`verify_plan`'s S1/S4/S5/S7, plus the emitter's own S2/S3/S6/S9/S10 --
    `_emit_decoupled` raises `AssertionError` on any violation, so a successful
    return IS the self-check passing) and remains byte-stable (double-run,
    shuffled-input-dict) -- title/arm-label text substitution has no bearing on
    any D7-checked structural property (edge conservation, port-id uniqueness,
    ingress out-degree, style/classDef presence).

    A regression trip-wire independent of D8's own title/arm-label substitution
    change in `decouple.py`/`component_graph.py` -- the substitution has no bearing
    on structural self-check or byte-stability. Mirrors `TestByteStability` above;
    kept as its own class because it is a D8-specific claim (self-check survives a
    title-rendering change), not a general determinism claim.
    """

    def test_live_corpus_decoupled_emission_passes_self_check(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        # _emit_decoupled() raises AssertionError on any D7 violation (S1-S10); a
        # successful return with non-empty text IS the self-check passing.
        text = graph._emit_decoupled(plan)
        assert text

    def test_live_corpus_decoupled_emission_stays_byte_stable_across_repeated_runs(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text_1 = graph._emit_decoupled(plan)
        text_2 = graph._emit_decoupled(plan)
        assert text_1 == text_2

    def test_live_corpus_decoupled_emission_stays_byte_stable_across_shuffled_input_dicts(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()

        rng = random.Random(20260726)
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


class TestD8AspectMarkerTitleSubstitution:
    """
    `_decoupled_member_lines()`'s aspect-marker
    branch (`TestAspectVisualMarker` above, ADR-036 D3/D4) independently reads
    `self.components[member_id].title` to build its second label line -- a
    distinct interpolation site from both the plain-node branch (`TestD8Acronym
    SubstitutionCaseInsensitivityAndScope`) and the PEP-wrap branch (`TestD8Pep
    WrapTitleSubstitutionLiveCorpus`). The live corpus's only lifted aspect
    (`componentAuditRecordRepository`) has no PEP phrase in its title, so neither the live
    corpus nor any test above exercises this branch with the phrase present --
    even `TestD8SelfCheckAndDeterminismUnaffected`'s global "phrase never
    survives" style guard is blind to it, since it never lifts an aspect whose
    title contains the phrase.

    This synthetic fixture is both aspect-lifted (so `_decoupled_member_lines()`
    takes the aspect-marker branch, not the plain-node branch) AND titled with
    the PEP phrase, isolating this one branch.
    """

    def test_aspect_marker_title_containing_pep_phrase_is_substituted(self, repo_root: Path):
        """
        `_aspect_marker_components(3)` builds a single lifted sink
        (`componentAspectSink`) with the fixed "Test Node" title
        (`TestAspectVisualMarker.test_synthetic_fixture_known_count_declares_node_
        with_class_and_two_line_label`'s baseline) -- overridden here with a title
        containing the PEP phrase, keeping the rest of the fixture (category,
        edges, lifted-edge count) identical so only the title varies.
        """
        components = _aspect_marker_components(3)
        components["componentAspectSink"] = _titled_node(INFRA, "Ingress Policy Enforcement Point", to_edges=[])
        forward_map = _forward_map(components)
        cfg = _aspect_marker_cfg(3)
        plan = build_decoupled_plan(forward_map, components, cfg)
        assert len(plan.lifted_aspects[0].edges) == 3, "sanity: unaffected by the title override"
        graph = _make_graph(components, forward_map, cfg, repo_root)

        text = graph._emit_decoupled(plan)

        expected = "componentAspectSink[Ingress PEP<br/>3 writes lifted]:::aspectStyle"
        assert expected in text, (
            f"expected the aspect marker's title to substitute to 'PEP' while keeping the write-count "
            f"text and ':::aspectStyle' suffix intact; got:\n{text}"
        )


# ----------------------------------------------------------------------------
# ADR-036 D9: consult-class channel landing, emitted-text half. The transform-level
# assertions live in test_decouple_transform.py; this section proves the landing
# reaches `_decoupled_edges()`'s `{arm.port_id} --> {arm.landing_id}` line, and --
# using this file's reduced 12-concern live-corpus registry (`_live_emission_config()`)
# -- that the three data-class arms landing on a wrapped PEP are NOT moved.
#
# Real corpus facts (read off `build_decoupled_plan()` against the live registry,
# not assumed): exactly 8 arms land at a PEP-wrapped target. Five are consult-class
# ("identity & authz" -> agent network, application network, authorization, and tool
# network PEPs, plus "endpoint enumeration" -> the agent network PEP -- the tool
# registry's caller-side enumerated-endpoint consult, ADR-030 D14) and three are
# data-class ("tool calls" to the tool network PEP, plus "inference / serving"'s
# two arms to the agent and application network PEPs).
# ----------------------------------------------------------------------------


class TestD9ConsultLandingLiveCorpusEmittedText:
    """
    The five-and-three split against the live registry, asserted on the emitted
    Mermaid text rather than only on the IR -- a landing rule that stopped at the
    dataclass would leave the drawn diagram unchanged, which is the whole point.
    """

    CONSULT_LANDINGS = {
        "p_in_app_identity_authz_agent_network_policy_enforcement_point": (
            "componentAgentNetworkPolicyEnforcementPoint"
        ),
        "p_in_app_identity_authz_application_network_policy_enforcement_point": (
            "componentApplicationNetworkPolicyEnforcementPoint"
        ),
        "p_in_tools_identity_authz_authorization_policy_enforcement_point": (
            "componentAuthorizationPolicyEnforcementPoint"
        ),
        "p_in_tools_identity_authz_tool_network_policy_enforcement_point": (
            "componentToolNetworkPolicyEnforcementPoint"
        ),
        # ADR-030 D14 / ADR-036 D9: the tool registry's enumerated-endpoint consult
        # onto the agent network PEP. A single-target concern gets the bare port id
        # (no target suffix, per `_build_arms`'s multi_arm rule), unlike the four
        # `identity & authz` arms above which share their concern across several
        # targets.
        "p_in_app_endpoint_enumeration": "componentAgentNetworkPolicyEnforcementPoint",
    }

    def _arms_by_concern_and_target(self, plan: DecoupledPlan) -> dict[tuple[str, str], object]:
        return {
            (channel.concern, arm.target): arm
            for broadcast in plan.broadcasts
            for channel in broadcast.channels
            for arm in channel.arms
        }

    def test_five_consult_arms_are_drawn_into_the_component_not_the_in_port(self, repo_root: Path):
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        text = _make_graph(components, forward_map, cfg, repo_root)._emit_decoupled(plan)

        for port_id, landing in self.CONSULT_LANDINGS.items():
            assert f"    {port_id} --> {landing}" in text, (
                f"expected consult arm {port_id} to be drawn into the component {landing}"
            )
            wrapper = plan.pep_wrappers[landing]
            assert f"    {port_id} --> {wrapper.in_id}" not in text, (
                f"consult arm {port_id} must no longer be drawn into {wrapper.in_id}"
            )

    def test_three_data_arms_to_wrapped_peps_still_land_on_the_in_port(self, repo_root: Path):
        """
        The unaffected half, named exhaustively: `tool calls` and both
        `inference / serving` arms genuinely traverse their gate, so each must keep
        the D3 `_in` landing in both the IR and the emitted text. The registry has
        no `tool discovery` label -- its sole edge is the `endpoint enumeration`
        consult arm above, not a fourth member of this list (ADR-036 D9).
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        text = _make_graph(components, forward_map, cfg, repo_root)._emit_decoupled(plan)
        arms = self._arms_by_concern_and_target(plan)

        data_arms = [
            ("tool calls", "componentToolNetworkPolicyEnforcementPoint"),
            ("inference / serving", "componentAgentNetworkPolicyEnforcementPoint"),
            ("inference / serving", "componentApplicationNetworkPolicyEnforcementPoint"),
        ]
        # Scoped to the registry's own declared concern labels: `cfg` is the shared,
        # deliberately reduced fixture documented on `_live_emission_config()` --
        # two `identity & authz` source edges are left uncovered on purpose and fall
        # back to a synthesized per-cluster-pair label (also landing on `_in`, since
        # a fallback label is never consult-class), which is that fixture's own known
        # artifact, not part of what this test pins.
        declared_labels = {c.label for c in cfg.concerns}
        in_port_landings = {
            (channel.concern, arm.target)
            for broadcast in plan.broadcasts
            for channel in broadcast.channels
            for arm in channel.arms
            if channel.concern in declared_labels
            and arm.target in plan.pep_wrappers
            and arm.landing_id == plan.pep_wrappers[arm.target].in_id
        }
        assert in_port_landings == set(data_arms), (
            f"expected exactly these arms to land on a wrapper's `_in` port: {set(data_arms)!r}, "
            f"got {in_port_landings!r}"
        )
        for key in data_arms:
            concern, target = key
            arm = arms[key]
            wrapper = plan.pep_wrappers[target]
            assert arm.landing_id == wrapper.in_id, (
                f"data-class arm ({concern} -> {target}) must keep its `_in` landing, got {arm.landing_id!r}"
            )
            assert f"    {arm.port_id} --> {wrapper.in_id}" in text

    def test_exactly_five_wrapped_landings_moved_and_no_others(self, repo_root: Path):
        """
        Blast-radius pin: across the WHOLE live plan, the arms that land on a bare
        wrapped-PEP component id are exactly the five consult-class ones. A rule that
        over-applied (e.g. matching any concern mentioning identity, or any PDP-sourced
        edge) would add entries here.
        """
        components, forward_map = _live_corpus(repo_root)
        plan = build_decoupled_plan(forward_map, components, _live_emission_config())

        moved = {
            (channel.concern, arm.target)
            for broadcast in plan.broadcasts
            for channel in broadcast.channels
            for arm in channel.arms
            if arm.target in plan.pep_wrappers and arm.landing_id == arm.target
        }
        assert moved == {
            ("identity & authz", "componentAgentNetworkPolicyEnforcementPoint"),
            ("identity & authz", "componentApplicationNetworkPolicyEnforcementPoint"),
            ("identity & authz", "componentAuthorizationPolicyEnforcementPoint"),
            ("identity & authz", "componentToolNetworkPolicyEnforcementPoint"),
            ("endpoint enumeration", "componentAgentNetworkPolicyEnforcementPoint"),
        }

    def test_self_check_and_byte_stability_survive_the_new_landing(self, repo_root: Path):
        """
        D9 claims it disturbs no D7 invariant. `_emit_decoupled()` re-asserts the full
        acceptance rubric internally and raises on violation, so a clean double-run
        that also passes `verify_plan()` is that claim under test.
        """
        components, forward_map = _live_corpus(repo_root)
        cfg = _live_emission_config()
        plan = build_decoupled_plan(forward_map, components, cfg)
        verify_plan(plan, components)

        graph = _make_graph(components, forward_map, cfg, repo_root)
        assert graph._emit_decoupled(plan) == graph._emit_decoupled(plan)


class TestShippedBlockRendersAgainstTheLiveCorpus:
    """
    The gap `TestRealConfigValidates` (test_emission_config_schema.py) and the
    other tests in this file both leave open: every OTHER emitter test here
    renders a test-owned `EmissionConfig` (`_live_emission_config()` or a
    synthetic fixture), never the actual, committed
    `graphTypes.component.emission` block parsed through the production
    parser. A schema-valid but semantically-wrong shipped block (a concern
    whose `edges` were rewritten to the wrong pair, a dropped label) can pass
    every schema test and every test-owned-config emitter test in this file
    while still rendering broken output -- nothing here would catch it.

    This class closes that gap from the OUTPUT side: it renders the shipped
    registry through the real transform + emission pipeline and checks the
    output has the properties D5/D9 promise -- the emitter otherwise has no
    render test against the shipped block's shape. `TestRealConfigValidates` and
    `TestClosedConcernLabelVocabulary` (test_emission_config_schema.py) close
    the DATA side -- schema shape and label-vocabulary membership -- without
    rendering anything.

    `port_styles` is overlaid with `PLACEHOLDER_PORT_STYLES_WITH_ASPECT` after
    parsing, matching `_live_emission_config_with_aspect_style()`'s own
    established convention: rendering via `_emit_decoupled()` directly
    (bypassing the `mode` gate, the same way every other test in this class
    does) runs D7's S6 self-check, which requires a `port` style whenever the
    plan draws ports, and the aspect marker (D3/D4) is gated on `aspectStyle`
    being configured. Supplying the placeholder isolates this class's
    assertions to the shipped `aspects`/`concerns` content, independent of
    whatever `portStyles` the live file currently declares.
    """

    def _shipped_cfg(self, repo_root: Path) -> EmissionConfig:
        with open(repo_root / "risk-map" / "yaml" / "mermaid-styles.yaml", encoding="utf-8") as fh:
            styles_doc = yaml.safe_load(fh)
        raw_emission = styles_doc.get("graphTypes", {}).get("component", {}).get("emission")
        assert raw_emission is not None, (
            "graphTypes.component.emission is missing from the live mermaid-styles.yaml"
        )
        parsed = _parse_emission_config(raw_emission)
        return dataclasses.replace(parsed, port_styles=PLACEHOLDER_PORT_STYLES_WITH_ASPECT)

    def test_every_channelled_concern_label_appears_in_the_rendered_output(self, repo_root: Path):
        """
        Given: the shipped block, parsed through `_parse_emission_config`
               (the same production parser CI's emission-drift check uses),
               and rendered against the live corpus
        When: the emitted Mermaid text is inspected
        Then: every concern label the shipped block declares appears in its
              own EGRESS PORT declaration line, in the exact grammar
              `TestPortAndComponentNodeDeclarations.
              test_egress_port_node_declared_with_adr_mockup_grammar` pins
              (`<port_id>["▸ <label>  ⇢ <arm_count>"]:::port`) -- a concern
              that never reaches a rendered broadcast is either unreferenced
              dead config or a broadcast-grouping defect, either of which
              this pins against

        A plain `label in text` substring check is vacuous here: every
        channelled label also appears in each of its own arms' INGRESS port
        lines (`<port_id>["<label> ▸"]:::port`), so blanking the egress
        line's label leaves the substring satisfied by the ingress side.
        Matching the full egress line grammar closes that
        gap: only the egress side's label is asserted, and matching the
        literal `▸ {label}  ⇢ {arm_count}` shape (not a bare substring) means
        a blanked or malformed egress label fails here even though the
        ingress side's copy of the same string remains in the text.
        """
        cfg = self._shipped_cfg(repo_root)
        components, forward_map = _live_corpus(repo_root)
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)
        text = graph._emit_decoupled(plan)

        rendered_labels = {broadcast.label for broadcast in plan.broadcasts}
        declared_labels = {c.label for c in cfg.concerns}
        missing = declared_labels - rendered_labels
        assert not missing, (
            f"Shipped emission.concerns label(s) {sorted(missing)} never reach a rendered "
            f"broadcast -- either dead config or every one of their edges failed to survive "
            f"the transform"
        )
        for broadcast in plan.broadcasts:
            expected = f'{broadcast.egress_port_id}["▸ {broadcast.label}  ⇢ {broadcast.arm_count}"]:::port'
            assert expected in text, (
                f"expected the egress port declaration {expected!r} for concern {broadcast.label!r}; got:\n{text}"
            )

    def test_aspect_marker_is_present_for_the_shipped_sink(self, repo_root: Path):
        """
        Given: the shipped block's declared aspect (the audit-record sink)
        When: rendered against the live corpus
        Then: the sink node carries the `:::aspectStyle` marker (D3/D4) in
              the output -- proving the shipped `aspects` entry, not just a
              test-owned stand-in, actually drives the lifted-aspect visual
              path end to end
        """
        cfg = self._shipped_cfg(repo_root)
        assert cfg.aspects, "expected the shipped block to declare at least one aspect"
        components, forward_map = _live_corpus(repo_root)
        plan = build_decoupled_plan(forward_map, components, cfg)
        graph = _make_graph(components, forward_map, cfg, repo_root)
        text = graph._emit_decoupled(plan)

        assert len(plan.lifted_aspects) == 1, "expected the shipped block to lift exactly the one declared sink"
        aspect_id = plan.lifted_aspects[0].aspect_id
        assert f"{aspect_id}[" in text, f"expected a node declaration for the lifted aspect {aspect_id!r}"
        assert ":::aspectStyle" in text, "expected the aspectStyle marker class on the lifted aspect node"


"""
Test Summary
============
Total test classes: 37 (95 test functions).

Emitter and self-check coverage:
- get_emission_config() accessor: 11 tests.
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

Additional coverage:
- TestPepWrapperRendering (wrap subgraph, in/out ports + pepport class, PEP node
  itself, port-chain edge + ordering): 4 tests.
- TestBlockRendering (nested block subgraph span, entry->exit invisible link,
  ordinary block-member placement): 3 tests. Also strengthens the existing
  `test_emitted_band_links_never_span_two_roots` (see its docstring) and extends the
  shared `_port_root_map` helper -- both changes, not new tests, so not counted here.
- TestPortAndComponentNodeDeclarations (egress port grammar, ingress port
  bare/suffixed grammar, ingress->landing edge, ordinary node title convention): 4
  tests.
- TestDegenerateEmptyPlans (all-intra corpus, no header noise, no orphaned port
  classes): 1 test.
- TestSingleArmBareGrammar (bare header + unsuffixed port id, arm_count=1): 1 test.
- TestS2ReverseDirectionMismatch (more arms present than declared): 1 test.
- TestSpecialCharacterHandling (bracket character in a component title): 1 test.
- TestOutputOrderSpanContract (span-level ordering on the live corpus: last
  subgraph 'end' before first '~~~'; last classDef before first ':::' usage): 2 tests.
  Requires `_SUBGRAPH_END_RE` to carry `re.MULTILINE` -- without it, `.finditer(text)`
  over the whole multi-line document matches zero times and the test fails
  unconditionally, for the wrong reason, regardless of implementation correctness
  (see the inline comment on `_SUBGRAPH_END_RE` for the verification).

Further coverage:
- TestIngressLandingAtPepWrappedTarget -- an ingress->landing edge
  whose arm target is PEP-wrapped, proving the edge retargets through the wrapper's
  `_in` port rather than landing at the raw PEP id: 1 test.
- TestPepWrapNestedInsideBlock -- triple subgraph containment (wrap nested in
  block nested in cluster), the live corpus's actual PEP placement: 1 test.
- TestConcernLabelEscaping -- an embedded `"` in a concern label, escaped as
  Mermaid's `#quot;` entity in quoted port labels but passed through literally in `%%`
  header comments (design decision documented in the class docstring): 1 test.
- TestAspectVisualMarker (ADR-036 D3/D4: `aspectStyle` class + "N writes lifted"
  second label line on a lifted aspect node, two-simultaneous-lift independence,
  and the fallback to a plain node when `aspectStyle` is not configured): 7 tests.
- TestShippedBlockRendersAgainstTheLiveCorpus -- renders the shipped
  `graphTypes.component.emission` block (not a test-owned fixture) through the real
  transform + emission pipeline: every channelled concern label appears in the
  output, and the aspect marker is present for the shipped sink: 2 tests.

Scope notes:
- Most tests call `ComponentGraph._emit_decoupled()` directly, exercising the real
  implementation.
- `TestModeDispatchIntegration` and the flat-regression/bypass tests call the public
  `build_graph()`/`to_mermaid()` entry points instead, to pin the dispatch
  integration itself.
- The header-format assertions (aspect-inventory grouping, band style ids) encode this
  suite's OWN chosen line-format contracts where ADR-036 D4 only requires a
  "grouped header-comment inventory"; the hop-list format is the
  one ADR-literal reproduction.
- No test presumes a specific channel-order-within-broadcast (the ADR mockup's own
  Model-before-Application display order is not the sorted order D7's "all iteration
  is sorted" byte-stability rule would produce)
  -- see `test_undrawn_hop_list_matches_adr_d6_mockup_literally`'s inline note.

Coverage of four cross-wiring/validation classes an IR-only check cannot catch
(every test below exercises the built text or the config accessor directly):
- `TestSourceEgressResolvesThroughPepWrapper` -- a PEP-wrapped broadcast
  source resolves its source->egress edge through `plan.pep_wrappers[src].out_id`,
  not the raw component id. Three tests pin the resolution (live-corpus `app +
  agent egress` two-PEP-source case, `tool results` single-PEP-source case, a
  synthetic mixed PEP/plain-source unit pin); one is a regression pin
  (`identity & authz`'s two non-PEP sources -- proves the resolution path is
  PEP-source-specific, not multi-source handling in general).
- `TestPlanWarningsSurfaced` -- `plan.warnings` (D7 guard output) is
  surfaced by `_emit_decoupled()`: logged via `logger.warning`; surfaced as a `%%`
  header comment, mirroring the existing S8-diagnostics precedent; must not alter
  drawn structure; and both `warnings` and `diagnostics` surface together when both
  are present.
- `TestSelfCheckCatchesGenuineEmitterDefects` -- S2 counts port declarations
  present in the built text (falling back to the IR arm count only when
  `plan.clusters` is empty) and S9/S10 match edges against the built text, not the
  IR. Each test simulates a genuine emitter defect by monkeypatching one of
  `_emit_decoupled()`'s own step methods: a dropped ingress-port declaration
  (text-derived S2), a cross-wired ingress->landing edge (S9), and a
  source->egress edge pointing at the wrong egress port id (S10, ties to
  `TestSourceEgressResolvesThroughPepWrapper`'s source-resolution logic above).
- `TestSelfChecksCatchS9S10ImplementationGaps` -- S9/S10 match against the built
  text with `_anchored_edge_pattern`, not a bare substring check: pins the
  prefix-collision case (an unanchored check would accept a cross-wired edge to a
  sibling id that extends the correct one) and S10's unfiltered reverse loop
  (flags any emitted edge to a port id outside `expected_pairs`, not only known
  ones). 2 tests.
- `TestGetEmissionConfigAccessor::test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat`
  -- a `concerns[n].edges` entry with the wrong tuple arity (3 or 1 elements, or a
  bare string, instead of `[src, tgt]`) is rejected by `_validated_edge()`, which
  raises `ValueError`; `get_emission_config()` catches it and degrades the whole
  block to `flat`. One parametrized case per malformed shape, matching the existing
  malformed-aspect-entry precedent (whole block degrades to `flat`).

`TestSourceEgressResolvesThroughPepWrapper`'s resolution is implemented entirely via
`component_graph.py`'s `plan.pep_wrappers` lookups, the same
pattern `Arm.landing_id` uses on the target side -- `decouple.py` is
untouched by it.

ADR-036 D1: "Band ports are not chained together with invisible
ordering links" (port-to-port `~~~` chaining removed; only a block's entry->exit pair
survives) -- implemented in `decouple.py`'s `_build_band_links`, tests below pin it:
- `TestBandLinksNeverSpanRoots.test_plan_band_links_never_span_two_roots` and
  `.test_emitted_band_links_never_span_two_roots` assert both the root-scoping
  property and that no band link ever touches a port id. The emitted-text test also
  pins the total `~~~` line count to exactly the number of block entry/exit pairs (4 in
  the live corpus).
- `TestBlockRendering.test_block_entry_exit_invisible_link_emitted` covers the
  narrower block-entry/exit case D1 does not affect,
  distinguished from the port-chain case in the two tests above.
- `TestOutputOrderContract.test_all_eight_steps_appear_in_the_fixed_relative_order`
  uses a `_small_synthetic_components_with_block()` fixture (extends the
  existing small-synthetic fixture with one block) and a literal
  `f"{block.entry_id} ~~~ {block.exit_id}"` marker instead of a bare `"~~~"` lookup
  -- the base fixture has no blocks, so with port-chaining removed it would emit
  zero `~~~` lines at all and this Step-7 marker would never be found otherwise.
- Two unit-level regression tests in `test_decouple_transform.py`'s
  `TestBandsAndBlocks` (`test_multiple_egress_ports_sharing_a_root_are_never_chained`,
  `test_multiple_ingress_ports_sharing_a_root_are_never_chained`) and one
  corpus-scale regression guard in `TestLiveCorpusInventory`
  (`test_band_links_are_block_entry_exit_pairs_only_no_port_chains`, pinning
  `plan.band_links` to exactly the 4 live-corpus block entry/exit pairs) pin the
  same fix in `_build_band_links`.
- `verify_plan()` (D7 self-check, `decouple.py`) and `component_graph.py`'s emission
  self-check have no dependency on port-to-port chain links:
  `verify_plan()`'s S1/S4/S5/S7 checks never
  reference `band_links` at all; `component_graph.py`'s S2/S3/S6 checks are keyed off
  `plan.broadcasts`/`plan.pep_wrappers`, not `plan.band_links`.

ADR-036 D8 (display-layer acronym substitution, "policy enforcement point"
-> "PEP", node titles only -- implemented in both `decouple.py` and
`component_graph.py`; the corresponding `decouple.py` arm-label coverage lives in
test_decouple_transform.py's own D8 section):
- `TestD8PepWrapTitleSubstitutionLiveCorpus` -- live corpus: a sanity pin of the 4
  real, unsubstituted PEP titles (documents the facts the next test's expectations
  are derived from), then all 4 substitute at both
  `_decoupled_pep_wrap_lines()` positions (wrap header, PEP node line), each keeping
  its own distinguishing prefix, plus a global "phrase never survives
  anywhere in the emitted text" guard. 3 tests.
- `TestD8PdpTitleGuardLiveCorpus` -- the real, non-PEP-wrapped
  `componentAuthorizationPolicyDecisionPoint` renders its spelled-out title
  unchanged (regression guard -- PDP is explicitly out of the D8 set). 1 test.
- `TestD8AcronymSubstitutionCaseInsensitivityAndScope` -- synthetic fixtures: (a)
  arbitrary mixed-case source text still substitutes (case-insensitivity beyond the
  two casings the live corpus/`target_short_name()` happen to produce), (b) an
  ORDINARY (non-PEP-id) node's title substitutes too, proving the overlay is
  unconditional on PEP-wrap id matching, (c) PDP and PEP side by side in the same
  document, ruling out a naive "Policy * Point" pattern, (d)
  the PLURAL phrase "Policy Enforcement Points" renders completely unchanged, ruling
  out a naive non-word-boundary-anchored match. 4 tests.
- `TestD8SelfCheckAndDeterminismUnaffected` -- the full live-corpus decoupled
  emission still passes every D7 self-check and stays byte-stable (double-run,
  shuffled-input-dict); title/arm-label substitution has no bearing on any
  D7-checked structural property. 3 tests, a D8-specific regression trip-wire.
- `TestD8AspectMarkerTitleSubstitution` -- the aspect-marker
  branch of `_decoupled_member_lines()` independently interpolates `title` into its
  second label line; no other test (live-corpus or synthetic) exercises this
  branch with a PEP-phrase title, since the live corpus's sole lifted aspect
  (`componentAuditRecordRepository`) has none. A synthetic fixture that is both aspect-lifted
  and PEP-titled closes the gap. 1 test.

ADR-036 D9 (consult-class channel landing, emitted-text half):
- `TestD9ConsultLandingLiveCorpusEmittedText` -- against this file's reduced
  12-concern live-corpus registry: the five consult-class arms (the four
  `identity & authz` PEP targets plus the `endpoint enumeration` registry consult
  onto the agent network PEP, ADR-030 D14 -- the tool registry's caller-side
  enumerated-endpoint consult, not a fourth `identity & authz` target) are drawn
  into their component ids and no longer into the wrapper's `_in`; the three
  remaining data-class arms landing on a wrapped PEP (`tool calls`, both
  `inference / serving` arms) keep `_in` in both the IR and the text; the set of
  arms landing on a bare wrapped component id is exactly those five consult arms
  and nothing else (blast-radius pin); and the D7 self-check plus byte stability
  survive the landing. 4 tests. The transform-level half lives in
  test_decouple_transform.py, and the consult-set/shipped-registry coupling pin in
  test_emission_config_schema.py.

Total: 12 tests across five classes, all pinning the D8 acronym-substitution
implementation.

Additional D8 coverage beyond the 16-test D8 suite (12 in this file + the
arm-label site's own 4 in `test_decouple_transform.py`): word-boundary/phrase-exactness
(this file's `TestD8AcronymSubstitutionCaseInsensitivityAndScope`,
plural-phrase test) and the aspect-marker branch under a PEP-phrase title (this file's
`TestD8AspectMarkerTitleSubstitution`).
"""
