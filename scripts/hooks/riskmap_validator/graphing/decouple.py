"""
Decoupled component-graph transform (ADR-036 D1-D7).

Pure-data transform layer between the validator's `forward_map`/`components` adjacency
maps and the Mermaid emission pass. Classifies every `components.yaml` edge as:

- an intra-cluster drawn edge (same `category` on both ends, D1),
- a lifted aspect edge (a cross in-edge into a declared observability sink, D4), or
- a channelled cross edge, grouped into channels/broadcasts by trust concern (D2, D5)
  and split into one arm per distinct target (D6), landing on the target's PEP wrapper
  `_in` port or, for a consult-class concern, on the target component itself (D9).

No Mermaid strings are produced here -- that is the emission pass (Phase 2,
`component_graph.py`). This module emits only the intermediate representation (IR)
dataclasses and the two public entry points that consume it:

    build_decoupled_plan(forward_map, components, emission_cfg) -> DecoupledPlan
    check_emission_drift(forward_map, components, emission_cfg) -> list[str]
    verify_plan(plan, components) -> None

Both public functions share a single internal classification pass (`_classify`) so a
warning that appears in `DecoupledPlan.warnings` and a warning returned by
`check_emission_drift` are always computed by the exact same logic (single source of
truth for the D7 guard table).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..models import ComponentNode

logger = logging.getLogger(__name__)

# ============================================================================
# Grammar constants (§E)
# ============================================================================

_COMPONENT_PREFIX = "component"
_CATEGORY_PREFIX = "components"

_PEP_ID_SUFFIX = "PolicyEnforcementPoint"
_PEP_ID_PATTERN = re.compile(r".*PolicyEnforcementPoint$")
_ENTRY_HANDLING_PATTERN = re.compile(r".*InputHandling$")
_EXIT_HANDLING_PATTERN = re.compile(r".*OutputHandling$")

# D6-normative abbreviations for the four current top-level categories; a future
# category falls back to lowercase-minus-prefix (root_slug()).
_ROOT_SLUGS = {
    "componentsInfrastructure": "infra",
    "componentsModel": "model",
    "componentsApplication": "app",
    "componentsExternalTools": "tools",
}

# Config-path fragments used in guard messages (plan §D message contract).
ASPECTS_CONFIG_PATH = "graphTypes.component.emission.aspects"
CONCERNS_CONFIG_PATH = "graphTypes.component.emission.concerns"

# ADR-036 D9: closed, fixed-in-code set of consult-class concern labels. An arm
# carrying one of these lands on its target component rather than on the target's
# PEP wrapper `_in` port -- the enforcement point consumes a policy verdict or
# identity attributes, it does not pass them through to a destination, so drawing
# them into the inbound gate would read as a second request stream.
#
# Keyed on the concern label because `emission.concerns` already partitions cross
# edges by exactly that judgment; no schema field is added. The label lives in
# config and this set lives in code, so the two are pinned against each other by a
# test over the shipped registry rather than by a runtime guard -- at transform time
# a missing label is indistinguishable from a config that legitimately has no
# consult-class concern (see ADR-036 D9). Growing this set past a couple of labels is
# D9's trip-wire to promote it to a declared per-concern config field.
CONSULT_CONCERN_LABELS = frozenset({"identity & authz"})

_CAMEL_SPLIT_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")


def slug(text: str) -> str:
    """
    Slugify a concern/aspect label for use in a port id.

    Lowercases, drops '&' entirely (not replaced), collapses any run of
    non-alphanumeric characters to a single '_', and trims leading/trailing '_'.

    Known gap (M6): two differently-worded concern labels that slug identically
    (e.g. "tool/hosting" and "tool hosting") are not detected here -- the resulting
    port ids collide. Registration-time uniqueness is deferred to Phase 2's
    `verify_plan`/S7 self-check rather than fixed in this function; see
    `build_decoupled_plan`'s docstring for the full rationale.

    Example:
        >>> slug("identity & authz")
        'identity_authz'
        >>> slug("inference / serving")
        'inference_serving'
    """
    lowered = text.lower().replace("&", "")
    collapsed = re.sub(r"[^a-z0-9]+", "_", lowered)
    return collapsed.strip("_")


def root_slug(category_id: str) -> str:
    """
    Abbreviate a top-level category id for port-id construction (D6/§E).

    The four current categories use fixed abbreviations; an unrecognized (future)
    category falls back to lowercase of the id minus the 'components' prefix.
    """
    if category_id in _ROOT_SLUGS:
        return _ROOT_SLUGS[category_id]
    return category_id.removeprefix(_CATEGORY_PREFIX).lower()


def target_short_name(component_id: str) -> str:
    """
    Derive a human-readable short name from a component id (§E).

    Strips the 'component' prefix, splits on camel-case word boundaries, and
    lowercases and space-joins the segments. Id-derived, not title-derived -- this
    is deliberately the full uncompressed name (e.g. "authorization policy
    enforcement point"), not an abbreviation.
    """
    stripped = component_id.removeprefix(_COMPONENT_PREFIX)
    segments = [seg for seg in _CAMEL_SPLIT_PATTERN.split(stripped) if seg]
    return " ".join(seg.lower() for seg in segments)


# ADR-036 D8: closed, fixed-in-code display-layer acronym set. A single
# declared term today ("policy enforcement point" -> "PEP"); "policy decision
# point" is deliberately excluded (see ADR-036 D8). Growing this set is a
# reviewed edit, not a pattern a future contributor extends ad hoc.
#
# Word-boundary anchored on both ends: an unanchored trailing match would also
# catch inside the plural "policy enforcement points" and wrongly collapse it
# (to "PEPs", or "PEP" with a dangling "s") -- the plural is a different phrase
# and must render unchanged.
_DISPLAY_ACRONYM_RE = re.compile(r"\bpolicy enforcement point\b", re.IGNORECASE)


def apply_display_acronyms(text: str) -> str:
    """
    Substitute the closed ADR-036 D8 acronym set into a display string.

    Display-time only -- never call this on `slug()`, `target_short_name()`'s
    id-derivation path, or `pep_wrap_base()`. Those feed port/id construction
    and must stay byte-stable regardless of display-layer wording (D7).
    """
    return _DISPLAY_ACRONYM_RE.sub("PEP", text)


def pep_wrap_base(component_id: str) -> str:
    """
    Derive the base string used to build a PEP wrapper's `_in`/`_out`/`_wrap` ids.

    Strips the 'component' prefix, abbreviates a trailing 'PolicyEnforcementPoint'
    to 'Pep', and lowercases the first character.

    Example:
        >>> pep_wrap_base("componentAgentNetworkPolicyEnforcementPoint")
        'agentNetworkPep'
    """
    stripped = component_id.removeprefix(_COMPONENT_PREFIX)
    if stripped.endswith(_PEP_ID_SUFFIX):
        stripped = stripped[: -len(_PEP_ID_SUFFIX)] + "Pep"
    if not stripped:
        return stripped
    return stripped[0].lower() + stripped[1:]


# ============================================================================
# IR dataclasses (plan §A)
# ============================================================================


@dataclass(frozen=True)
class AspectDecl:
    """One `emission.aspects` registry entry: a declared sink component and its guard threshold."""

    id: str
    min_cross_in_degree: int


@dataclass(frozen=True)
class ConcernDecl:
    """One `emission.concerns` registry entry: a trust-concern label and the edges it covers."""

    label: str
    edges: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class EmissionConfig:
    """Parsed `graphTypes.component.emission` config block (D3)."""

    mode: str
    aspects: tuple[AspectDecl, ...] = ()
    concerns: tuple[ConcernDecl, ...] = ()
    port_styles: dict[str, str] | None = None


@dataclass(frozen=True)
class PepWrapper:
    """The visual wrap treatment for a policy-enforcement-point node (D1/D3)."""

    pep_id: str
    in_id: str
    out_id: str
    wrap_id: str


@dataclass(frozen=True)
class Arm:
    """One channel arm: a single distinct landing target and its member edges (D6)."""

    target: str
    landing_id: str
    port_id: str
    label: str
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Channel:
    """Cross edges keyed by (src_root, tgt_root, concern), split into arms (D2, D6)."""

    src_root: str
    tgt_root: str
    concern: str
    edges: tuple[tuple[str, str], ...]
    arms: tuple[Arm, ...]


@dataclass(frozen=True)
class Broadcast:
    """Channels sharing (src_root, concern) merged behind one egress port (D2)."""

    egress_port_id: str
    src_root: str
    label: str
    channels: tuple[Channel, ...]
    arm_count: int


@dataclass(frozen=True)
class LiftedAspect:
    """A successfully lifted aspect and the cross in-edges removed into its header inventory (D4)."""

    aspect_id: str
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Block:
    """A subcategory subgraph nested inside a cluster."""

    id: str
    members: tuple[str, ...]
    entry_id: str | None
    exit_id: str | None
    pure_feeders: frozenset[str]
    exit_skips: frozenset[str]


@dataclass(frozen=True)
class Cluster:
    """A top-level category subgraph: its direct members plus its nested blocks."""

    id: str
    members: tuple[str, ...]
    blocks: dict[str, Block]


@dataclass
class DecoupledPlan:
    """
    The full transform output: everything the Phase 2 emission pass needs to
    serialize Mermaid text, plus the D7 conservation counters, warnings, and the
    step-8 reachability diagnostic (M3). `diagnostics` is strictly advisory: it never
    affects `warnings` or any drawn-output field (arms, channels, edges, bands).
    """

    clusters: dict[str, Cluster]
    pep_wrappers: dict[str, PepWrapper]
    broadcasts: tuple[Broadcast, ...]
    lifted_aspects: list[LiftedAspect]
    drawn_intra_edges: list[tuple[str, str]]
    collapsed_pairs: list[tuple[str, str]]
    band_links: list[tuple[str, str]]
    warnings: list[str]
    diagnostics: list[str]
    intra_drawn_count: int
    collapsed_pair_count: int
    channelled_count: int
    lifted_count: int
    total_edges: int


# ============================================================================
# Step 1: partition (D2)
# ============================================================================


def _partition_edges(
    forward_map: dict[str, list[str]], components: dict[str, ComponentNode]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """Split every forward_map edge into intra/cross by root(n) = components[n].category."""
    all_edges = sorted((src, tgt) for src, targets in forward_map.items() for tgt in targets)
    intra_edges = []
    cross_edges = []
    for src, tgt in all_edges:
        if components[src].category == components[tgt].category:
            intra_edges.append((src, tgt))
        else:
            cross_edges.append((src, tgt))
    return all_edges, intra_edges, cross_edges


# ============================================================================
# Step 2: aspect lift (D4) + its guards (G-A1, G-A2, G-A3, G-O1)
# ============================================================================


def _block_members(node: ComponentNode, components: dict[str, ComponentNode]) -> set[str]:
    """All components sharing `node`'s (category, subcategory) -- i.e. its block."""
    return {
        cid
        for cid, other in components.items()
        if other.category == node.category and other.subcategory == node.subcategory
    }


def _evaluate_aspects(
    components: dict[str, ComponentNode],
    cross_edges: list[tuple[str, str]],
    intra_edges: list[tuple[str, str]],
    emission_cfg: EmissionConfig,
) -> tuple[list[LiftedAspect], set[tuple[str, str]], list[str]]:
    """
    Evaluate every `emission.aspects` entry against D4 candidacy and the D7
    block-orphan guard (G-O1). Returns the successfully-lifted aspects, the set of
    edges they remove from channel consideration, and any guard warnings.
    """
    lifted_aspects: list[LiftedAspect] = []
    lifted_edges: set[tuple[str, str]] = set()
    warnings: list[str] = []

    for decl in sorted(emission_cfg.aspects, key=lambda d: d.id):
        aspect_id = decl.id

        if aspect_id not in components:
            warnings.append(
                f"{ASPECTS_CONFIG_PATH}: aspect id '{aspect_id}' not found in the corpus -- "
                f"no matching component in components.yaml; this entry is stale and is ignored. "
                f"Remove it or correct the id."
            )
            continue

        node = components[aspect_id]
        out_edges = sorted(t for s, t in _edges_from(aspect_id, cross_edges, intra_edges))
        if out_edges:
            warnings.append(
                f"{ASPECTS_CONFIG_PATH}: aspect '{aspect_id}' has outgoing edge(s) to "
                f"{', '.join(out_edges)}, violating the D4 sink condition (total out-degree "
                f"must be 0); the lift is refused and its edges are reclassified as a channel. "
                f"Remove the outgoing edge(s) or de-register this aspect."
            )
            continue

        cross_in = sorted((s, t) for s, t in cross_edges if t == aspect_id)
        if len(cross_in) < decl.min_cross_in_degree:
            warnings.append(
                f"{ASPECTS_CONFIG_PATH}: aspect '{aspect_id}' has cross in-degree "
                f"{len(cross_in)}, below its configured minCrossInDegree "
                f"({decl.min_cross_in_degree}); the lift is refused and its edges are "
                f"reclassified as a channel. Lower minCrossInDegree or remove this entry "
                f"if the aspect no longer qualifies."
            )
            continue

        if node.subcategory is not None:
            block = _block_members(node, components)
            block_has_intra_edge = any(s in block or t in block for s, t in intra_edges)
            if not block_has_intra_edge:
                warnings.append(
                    f"{ASPECTS_CONFIG_PATH}: lifting aspect '{aspect_id}' would leave its "
                    f"block '{node.subcategory}' with zero drawn intra edges; the lift is "
                    f"refused and its edges are reclassified as a channel instead. Add an "
                    f"intra-cluster edge elsewhere in the block or remove this entry."
                )
                continue

        lifted_aspects.append(LiftedAspect(aspect_id=aspect_id, edges=tuple(cross_in)))
        lifted_edges.update(cross_in)

    return lifted_aspects, lifted_edges, warnings


def _edges_from(
    node_id: str, cross_edges: list[tuple[str, str]], intra_edges: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """All outgoing edges (intra or cross) originating at `node_id` -- the D4 total out-degree."""
    return [(s, t) for s, t in cross_edges if s == node_id] + [(s, t) for s, t in intra_edges if s == node_id]


# ============================================================================
# Step 3: concern resolution (§B step 3, guards G-C1/G-C2/G-C3/G-C4)
# ============================================================================


def _resolve_concern_coverage(
    all_edges: set[tuple[str, str]],
    cross_edges: set[tuple[str, str]],
    components: dict[str, ComponentNode],
    emission_cfg: EmissionConfig,
) -> tuple[dict[tuple[str, str], list[str]], list[str]]:
    """
    Validate every declared `emission.concerns` edge against the corpus (G-C1 dead
    reference, G-C2 now-intra recategorization) and build the edge -> [labels]
    coverage map used to resolve each remaining cross edge's concern.
    """
    coverage: dict[tuple[str, str], list[str]] = {}
    warnings: list[str] = []

    for idx, decl in enumerate(emission_cfg.concerns):
        for src, tgt in decl.edges:
            edge = (src, tgt)
            if edge not in all_edges:
                warnings.append(
                    f"{CONCERNS_CONFIG_PATH}[{idx}]: entry '{decl.label}' names edge "
                    f"({src}, {tgt}), which does not exist in the corpus -- {src} has no "
                    f"outgoing edge to {tgt} in components.yaml. Remove or correct this "
                    f"edge reference."
                )
                continue
            if edge not in cross_edges:
                category = components[src].category
                warnings.append(
                    f"{CONCERNS_CONFIG_PATH}[{idx}]: entry '{decl.label}' names edge "
                    f"({src}, {tgt}) as cross-boundary, but both endpoints now share "
                    f"category '{category}'; the edge is treated as intra and this "
                    f"reference is ignored. Remove or update this entry to match the "
                    f"current corpus."
                )
                continue
            coverage.setdefault(edge, []).append(decl.label)

    return coverage, warnings


def _resolve_edge_labels(
    remaining_cross_edges: list[tuple[str, str]],
    coverage: dict[tuple[str, str], list[str]],
    components: dict[str, ComponentNode],
) -> tuple[list[tuple[tuple[str, str], str]], list[str]]:
    """Resolve each remaining cross edge to a single concern label (G-C3 fallback, G-C4 tie-break)."""
    resolved: list[tuple[tuple[str, str], str]] = []
    warnings: list[str] = []

    for src, tgt in remaining_cross_edges:
        labels = coverage.get((src, tgt), [])
        if not labels:
            src_root = components[src].category
            tgt_root = components[tgt].category
            label = f"{src_root}→{tgt_root} flow"
            warnings.append(
                f"{CONCERNS_CONFIG_PATH}: no entry covers cross edge ({src}, {tgt}); "
                f"synthesizing fallback label '{label}'. Add an entry to "
                f"{CONCERNS_CONFIG_PATH} naming this edge."
            )
        elif len(labels) == 1:
            label = labels[0]
        else:
            label = min(labels)
            competing = ", ".join(sorted(labels))
            warnings.append(
                f"{CONCERNS_CONFIG_PATH}: cross edge ({src}, {tgt}) is covered by multiple "
                f"entries ({competing}); resolving to the lexicographically-first label "
                f"'{label}'. Remove the duplicate coverage so only one entry names this edge."
            )
        resolved.append(((src, tgt), label))

    return resolved, warnings


# ============================================================================
# Step 4-5: channel keying, broadcast grouping, arm splitting (D2, D5, D6)
# ============================================================================


def _build_arms(
    edges: tuple[tuple[str, str], ...],
    label: str,
    tgt_root: str,
    pep_wrappers: dict[str, PepWrapper],
    multi_arm: bool,
) -> tuple[Arm, ...]:
    """
    One arm per distinct target in this channel (D6): no landing selection, no
    reachability coverage.

    `multi_arm` is the bare-vs-suffixed decision and is passed in rather than computed
    from `edges` alone: D6/§B step 5 scope "the arm is its root's only arm for that
    concern" to (tgt_root, concern) across every channel landing there, not to this one
    channel's own edges. Two channels sharing (tgt_root, concern) but differing in
    src_root are otherwise invisible to each other's arm-count decision, so the caller
    (`_group_channels`) computes `multi_arm` from the union of targets across all
    channels sharing (tgt_root, concern) before calling this function.

    `landing_id` is the only field the D9 consult classification touches: `port_id` and
    `label` are computed from separate expressions below and stay byte-identical either
    way, preserving D7's content-derived-id stability.
    """
    by_target: dict[str, list[tuple[str, str]]] = {}
    for src, tgt in edges:
        by_target.setdefault(tgt, []).append((src, tgt))

    targets_sorted = sorted(by_target)
    root_abbrev = root_slug(tgt_root)
    concern_slug = slug(label)
    is_consult = label in CONSULT_CONCERN_LABELS

    arms = []
    for target in targets_sorted:
        member_edges = tuple(sorted(by_target[target]))
        if multi_arm:
            target_suffix = slug(target_short_name(target))
            # slug() collision note (M6): concern_slug/target_suffix collisions across
            # differently-worded labels are not checked here; see slug()'s docstring.
            port_id = f"p_in_{root_abbrev}_{concern_slug}_{target_suffix}"
            # ADR-036 D8: display-only substitution on the label; port_id above is
            # computed from a separate target_short_name() call and is untouched.
            arm_label = f"{label} → {apply_display_acronyms(target_short_name(target))}"
        else:
            # slug() collision note (M6): see slug()'s docstring -- this bare port id
            # can still collide with another concern's if the two labels slug identically.
            port_id = f"p_in_{root_abbrev}_{concern_slug}"
            arm_label = label
        # ADR-036 D9: a consult-class arm lands on the component itself even when the
        # target is wrapped -- the wrapper's `_in` port is for traffic that traverses
        # the gate. The PEP node is declared inside its wrap subgraph, so the arm still
        # terminates visibly at the enforcement point, just not through its inbound gate.
        if target in pep_wrappers and not is_consult:
            landing_id = pep_wrappers[target].in_id
        else:
            landing_id = target
        arms.append(
            Arm(target=target, landing_id=landing_id, port_id=port_id, label=arm_label, edges=member_edges)
        )

    return tuple(arms)


def _group_channels(
    resolved_edges: list[tuple[tuple[str, str], str]],
    components: dict[str, ComponentNode],
    pep_wrappers: dict[str, PepWrapper],
) -> list[Channel]:
    """
    Group resolved cross edges by (src_root, tgt_root, concern) (D2) and split arms (D6).

    The bare-vs-suffixed arm decision (D6) is scoped to (tgt_root, concern) across ALL
    channels landing there, not to one channel's own edges -- two channels sharing
    (tgt_root, concern) but differing only in src_root would otherwise each
    independently see themselves as single-arm and construct an identical bare label
    and port id, even though they land at different targets (H2). So the distinct-target
    union per (tgt_root, concern) is computed once, across every channel, before any
    channel's arms are built.
    """
    grouped: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    for (src, tgt), label in resolved_edges:
        key = (components[src].category, components[tgt].category, label)
        grouped.setdefault(key, []).append((src, tgt))

    targets_by_root_concern: dict[tuple[str, str], set[str]] = {}
    for (_src_root, tgt_root, label), edges in grouped.items():
        targets_by_root_concern.setdefault((tgt_root, label), set()).update(tgt for _src, tgt in edges)

    channels = []
    for (src_root, tgt_root, label), edges in sorted(grouped.items()):
        edges_sorted = tuple(sorted(edges))
        multi_arm = len(targets_by_root_concern[(tgt_root, label)]) > 1
        arms = _build_arms(edges_sorted, label, tgt_root, pep_wrappers, multi_arm)
        channels.append(
            Channel(src_root=src_root, tgt_root=tgt_root, concern=label, edges=edges_sorted, arms=arms)
        )
    return channels


def _group_broadcasts(channels: list[Channel]) -> tuple[Broadcast, ...]:
    """Merge channels sharing (src_root, concern) behind one egress port (D2)."""
    grouped: dict[tuple[str, str], list[Channel]] = {}
    for channel in channels:
        grouped.setdefault((channel.src_root, channel.concern), []).append(channel)

    broadcasts = []
    for (src_root, label), member_channels in sorted(grouped.items()):
        ordered_channels = tuple(sorted(member_channels, key=lambda c: c.tgt_root))
        arm_count = sum(len(c.arms) for c in ordered_channels)
        # slug() collision note (M6): see slug()'s docstring -- two differently-worded
        # labels that slug identically produce the same egress port id here.
        egress_port_id = f"p_out_{root_slug(src_root)}_{slug(label)}"
        broadcasts.append(
            Broadcast(
                egress_port_id=egress_port_id,
                src_root=src_root,
                label=label,
                channels=ordered_channels,
                arm_count=arm_count,
            )
        )
    return tuple(broadcasts)


# ============================================================================
# Step 6: PEP wrap -> retarget -> collapse (D1, D3)
# ============================================================================


def _build_pep_wrappers(components: dict[str, ComponentNode]) -> dict[str, PepWrapper]:
    """Every component id matching `.*PolicyEnforcementPoint$` gets a wrapper, universally."""
    wrappers = {}
    for component_id in sorted(components):
        if _PEP_ID_PATTERN.match(component_id):
            base = pep_wrap_base(component_id)
            wrappers[component_id] = PepWrapper(
                pep_id=component_id, in_id=f"{base}_in", out_id=f"{base}_out", wrap_id=f"{base}_wrap"
            )
    return wrappers


def _process_intra_edges(
    intra_edges: list[tuple[str, str]], pep_wrappers: dict[str, PepWrapper]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Wrap -> retarget -> collapse, in that order (D1). A mirrored intra pair collapses
    to a single `collapsed_pairs` entry only when neither endpoint is PEP-wrapped;
    any edge touching a wrapped PEP is retargeted through its `_in`/`_out` port and
    never collapses, even if it is part of a mirrored pair.
    """
    original_set = set(intra_edges)
    handled: set[tuple[str, str]] = set()
    drawn: list[tuple[str, str]] = []
    collapsed: list[tuple[str, str]] = []

    for src, tgt in intra_edges:
        if (src, tgt) in handled:
            continue

        touches_pep = src in pep_wrappers or tgt in pep_wrappers
        reverse = (tgt, src)

        if reverse in original_set and not touches_pep and src != tgt:
            collapsed.append(tuple(sorted((src, tgt))))
            handled.add((src, tgt))
            handled.add(reverse)
            continue

        new_src = pep_wrappers[src].out_id if src in pep_wrappers else src
        new_tgt = pep_wrappers[tgt].in_id if tgt in pep_wrappers else tgt
        drawn.append((new_src, new_tgt))
        handled.add((src, tgt))

    return drawn, collapsed


# ============================================================================
# Step 7: bands / blocks (moderate depth, shared recipe mechanics)
# ============================================================================


def _in_block_degrees(
    block_members: tuple[str, ...], forward_map: dict[str, list[str]]
) -> tuple[dict[str, int], dict[str, int]]:
    """In-degree/out-degree of each block member counting only edges within the same block."""
    member_set = set(block_members)
    in_degree = {m: 0 for m in block_members}
    out_degree = {m: 0 for m in block_members}
    for src in block_members:
        for tgt in forward_map.get(src, []):
            if tgt in member_set:
                out_degree[src] += 1
                in_degree[tgt] += 1
    return in_degree, out_degree


def _build_block(subcategory: str, members: tuple[str, ...], forward_map: dict[str, list[str]]) -> Block:
    """Build one Block: entry/exit by the `.*(Input|Output)Handling$` regex, plus feeder/skip sets."""
    entry_id = next((m for m in members if _ENTRY_HANDLING_PATTERN.match(m)), None)
    exit_id = next((m for m in members if _EXIT_HANDLING_PATTERN.match(m)), None)
    in_degree, out_degree = _in_block_degrees(members, forward_map)
    pure_feeders = frozenset(m for m in members if in_degree[m] == 0)
    exit_skips = frozenset(m for m in members if out_degree[m] == 0 and m != exit_id)
    return Block(
        id=subcategory,
        members=members,
        entry_id=entry_id,
        exit_id=exit_id,
        pure_feeders=pure_feeders,
        exit_skips=exit_skips,
    )


def _build_clusters(components: dict[str, ComponentNode], forward_map: dict[str, list[str]]) -> dict[str, Cluster]:
    """Group components into clusters (by category) and, within each, blocks (by subcategory)."""
    roots = sorted({node.category for node in components.values()})
    clusters: dict[str, Cluster] = {}

    for root in roots:
        root_members = {cid for cid, node in components.items() if node.category == root}
        direct_members = tuple(sorted(cid for cid in root_members if components[cid].subcategory is None))
        subcategories = sorted(
            {components[cid].subcategory for cid in root_members if components[cid].subcategory is not None}
        )
        blocks = {}
        for subcategory in subcategories:
            block_members = tuple(
                sorted(cid for cid in root_members if components[cid].subcategory == subcategory)
            )
            blocks[subcategory] = _build_block(subcategory, block_members, forward_map)
        clusters[root] = Cluster(id=root, members=direct_members, blocks=blocks)

    return clusters


def _build_band_links(clusters: dict[str, Cluster]) -> list[tuple[str, str]]:
    """
    Invisible ordering links (D1's `~~~` pinning) for the emission pass: each block's
    entry->exit pair when both exist. Never spans two roots (D1).

    Port-to-port chain links (egress ports sharing a cluster, ingress ports sharing a
    cluster) are deliberately not built here. ADR-036 D1: a band's own subgraph
    nesting is what pins its ports to the container's edge (an ELK compound-node
    contiguity constraint) -- chaining the ports with `~~~` links was found to
    actively cause horizontal sprawl instead, since every port carries a
    boundary-crossing edge by definition, which makes ELK stamp `INCLUDE_CHILDREN`
    hierarchy handling on it and override the nested subgraph's own layout direction.
    A block's entry/exit pair is two real component nodes, not ports, so it is
    unaffected and is retained.
    """
    links: list[tuple[str, str]] = []
    for cluster in clusters.values():
        for block in cluster.blocks.values():
            if block.entry_id is not None and block.exit_id is not None:
                links.append((block.entry_id, block.exit_id))

    return links


# ============================================================================
# Step 8: reachability diagnostic (D2/D7 S8) -- advisory only, never raises
# ============================================================================


def _reachability_diagnostic(channels: list[Channel], intra_edges: list[tuple[str, str]]) -> list[str]:
    """
    Advisory-only diagnostic: finds multi-arm channels whose distinct arm targets are
    mutually intra-cluster reachable from one another, logs each finding, and returns
    the findings as messages (M3). Never raises and never writes to `plan.warnings` --
    reachability is explicitly demoted to a diagnostic, not a landing mechanism or a
    drift guard (D2). The pipeline (`_classify`) collects the returned list into
    `DecoupledPlan.diagnostics`; the caller passes `channels` in the same sorted order
    `_group_channels` produces, and each channel's `arms` are already target-sorted, so
    the returned message order is deterministic (D7).
    """
    adjacency: dict[str, set[str]] = {}
    for src, tgt in intra_edges:
        adjacency.setdefault(src, set()).add(tgt)

    def _reachable(start: str, goal: str) -> bool:
        seen = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for nxt in adjacency.get(node, ()):
                if nxt == goal:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    messages: list[str] = []
    for channel in channels:
        targets = [arm.target for arm in channel.arms]
        if len(targets) < 2:
            continue
        for i, target_a in enumerate(targets):
            for target_b in targets[i + 1 :]:
                if _reachable(target_a, target_b) and _reachable(target_b, target_a):
                    message = (
                        f"reachability diagnostic (advisory only): channel "
                        f"{channel.src_root}->{channel.tgt_root} concern={channel.concern!r} "
                        f"arms {target_a} and {target_b} are mutually intra-reachable"
                    )
                    logger.info(message)
                    messages.append(message)
    return messages


# ============================================================================
# Shared classification pass + public API
# ============================================================================


def _classify(
    forward_map: dict[str, list[str]],
    components: dict[str, ComponentNode],
    emission_cfg: EmissionConfig,
) -> dict:
    """
    Run the full 8-step pipeline (plan §B) once. Both public entry points
    (`build_decoupled_plan`, `check_emission_drift`) call this so a warning that
    appears in one is guaranteed to appear in the other.
    """
    warnings: list[str] = []

    all_edges, intra_edges, cross_edges = _partition_edges(forward_map, components)

    pep_wrappers = _build_pep_wrappers(components)

    lifted_aspects, lifted_edge_set, aspect_warnings = _evaluate_aspects(
        components, cross_edges, intra_edges, emission_cfg
    )
    warnings.extend(aspect_warnings)

    remaining_cross_edges = [edge for edge in cross_edges if edge not in lifted_edge_set]

    coverage, concern_warnings = _resolve_concern_coverage(
        set(all_edges), set(cross_edges), components, emission_cfg
    )
    warnings.extend(concern_warnings)

    resolved_edges, resolution_warnings = _resolve_edge_labels(remaining_cross_edges, coverage, components)
    warnings.extend(resolution_warnings)

    channels = _group_channels(resolved_edges, components, pep_wrappers)
    broadcasts = _group_broadcasts(channels)

    drawn_intra_edges, collapsed_pairs = _process_intra_edges(intra_edges, pep_wrappers)

    clusters = _build_clusters(components, forward_map)
    band_links = _build_band_links(clusters)

    diagnostics = _reachability_diagnostic(channels, intra_edges)

    return {
        "warnings": warnings,
        "diagnostics": diagnostics,
        "clusters": clusters,
        "pep_wrappers": pep_wrappers,
        "broadcasts": broadcasts,
        "lifted_aspects": lifted_aspects,
        "drawn_intra_edges": drawn_intra_edges,
        "collapsed_pairs": collapsed_pairs,
        "band_links": band_links,
        "intra_drawn_count": len(drawn_intra_edges),
        "collapsed_pair_count": len(collapsed_pairs),
        "channelled_count": len(remaining_cross_edges),
        "lifted_count": sum(len(la.edges) for la in lifted_aspects),
        "total_edges": len(all_edges),
    }


def build_decoupled_plan(
    forward_map: dict[str, list[str]],
    components: dict[str, ComponentNode],
    emission_cfg: EmissionConfig,
) -> DecoupledPlan:
    """
    Run the full transform pipeline (§B) and return the resulting IR.

    Deliberately does NOT call `verify_plan()` on the result. `verify_plan` is a strict
    self-check that raises on any D7 violation (S1/S4/S5/S7), including the known,
    documented slug-collision gap between distinct concern labels (M6): two differently
    -worded labels that happen to slug identically still produce colliding port ids,
    and callers who need to observe that plan (to inspect it, or to confirm the
    collision is representable) require `build_decoupled_plan` to succeed even though
    `verify_plan` would raise on it. Wiring `verify_plan` in here unconditionally would
    turn every M6-shaped input into a hard failure at construction time, before a caller
    ever gets a plan to inspect. Callers that want the D7 self-check should call
    `verify_plan(plan, components)` explicitly against the returned plan; the Phase 2
    emission pass re-asserts the full acceptance rubric (including the text-level
    checks `verify_plan` cannot see) as its own mandatory self-check.
    """
    parts = _classify(forward_map, components, emission_cfg)
    return DecoupledPlan(
        clusters=parts["clusters"],
        pep_wrappers=parts["pep_wrappers"],
        broadcasts=parts["broadcasts"],
        lifted_aspects=parts["lifted_aspects"],
        drawn_intra_edges=parts["drawn_intra_edges"],
        collapsed_pairs=parts["collapsed_pairs"],
        band_links=parts["band_links"],
        warnings=parts["warnings"],
        diagnostics=parts["diagnostics"],
        intra_drawn_count=parts["intra_drawn_count"],
        collapsed_pair_count=parts["collapsed_pair_count"],
        channelled_count=parts["channelled_count"],
        lifted_count=parts["lifted_count"],
        total_edges=parts["total_edges"],
    )


def check_emission_drift(
    forward_map: dict[str, list[str]],
    components: dict[str, ComponentNode],
    emission_cfg: EmissionConfig,
) -> list[str]:
    """Run the guard pass only (plan §D) and return the full warning list in one call."""
    return _classify(forward_map, components, emission_cfg)["warnings"]


def verify_plan(plan: DecoupledPlan, components: dict[str, ComponentNode]) -> None:
    """
    IR-level self-check (D7): raises `AssertionError` on any violation.

    Covers the IR-computable subset of the acceptance rubric -- edge conservation
    (S5), zero cross-root drawn edges (S1), port-id uniqueness (S7), and per-band
    ingress-label uniqueness (S4). The text-level assertions (S2, S3, S6) require the
    built Mermaid string and are re-asserted by the Phase 2 emission pass's own
    self-check.
    """
    conserved = plan.intra_drawn_count + 2 * plan.collapsed_pair_count + plan.channelled_count + plan.lifted_count
    if conserved != plan.total_edges:
        raise AssertionError(
            f"S5 edge conservation violated: intra_drawn({plan.intra_drawn_count}) + "
            f"2*collapsed({plan.collapsed_pair_count}) + channelled({plan.channelled_count}) + "
            f"lifted({plan.lifted_count}) = {conserved} != total_edges({plan.total_edges})"
        )

    for src, tgt in plan.drawn_intra_edges:
        # `src`/`tgt` may be a PEP wrapper's synthetic `_in`/`_out` port id (retargeted
        # by _process_intra_edges), not a real components.yaml id -- those are skipped
        # here rather than flagged, since an edge that reaches a wrapper port is by
        # construction intra (it was intra before wrapping; wrapping never changes an
        # edge's category membership), so there is nothing for this check to catch.
        if src in components and tgt in components and components[src].category != components[tgt].category:
            raise AssertionError(f"S1 violated: drawn intra edge ({src}, {tgt}) spans two roots")

    port_ids = [b.egress_port_id for b in plan.broadcasts]
    port_ids += [arm.port_id for b in plan.broadcasts for c in b.channels for arm in c.arms]
    duplicate_ports = {p for p in port_ids if port_ids.count(p) > 1}
    if duplicate_ports:
        raise AssertionError(f"S7 violated: port id collision(s): {sorted(duplicate_ports)}")

    labels_by_root: dict[str, list[str]] = {}
    for broadcast in plan.broadcasts:
        for channel in broadcast.channels:
            for arm in channel.arms:
                labels_by_root.setdefault(channel.tgt_root, []).append(arm.label)
    for root, labels in labels_by_root.items():
        duplicate_labels = {label for label in labels if labels.count(label) > 1}
        if duplicate_labels:
            raise AssertionError(
                f"S4 violated: duplicate ingress label(s) in band '{root}': {sorted(duplicate_labels)}"
            )
