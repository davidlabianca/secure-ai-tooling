# Component corpus fixture

**This is test input, not CoSAI Risk Map content.** It is a small, hand-authored, purpose-built
stand-in for `risk-map/yaml/components.yaml` (and, for the taxonomy and edge facts below, for the
parts of `risk-map/schemas/components.schema.json` that a case's verdict depends on), used only to
grade eval cases whose correct verdict depends on corpus- or schema-state facts — "does an existing
component already cover this candidate," "is this category/subcategory pairing valid," "do these two
components already share a direct edge" — never the live, growing corpus or the live schema (see
ADR-033 Amendment 2026-07-30, D7). It must not be cited, validated, or consumed as if it were real
Risk Map content. It is refreshed only if the component entity shape or the schema's
category/subcategory shape changes structurally (e.g. a required field is added, a category gains or
loses a valid subcategory), never in response to the real corpus growing or the real taxonomy being
extended.

## Fixture entries

- `componentFixtureToolInvocation` — the external APIs, services, and third-party integrations an
  agent invokes to take action in the world, including however those integrations are discovered,
  registered, or pulled into the agent's available tool set. **Deliberately broad enough to cover
  any external tool/service integration surface, including third-party tool discovery and
  registration** — a near-duplicate target for eval cases proposing a narrower slice of the same
  capability (e.g. a specific integration or registry mechanism).
- `componentFixtureMemoryStore` — persistent context and facts an agent or model retains across
  interactions, including isolation between different users' and tenants' stored context.
  **Deliberately broad enough to cover cross-user/cross-tenant memory isolation as an attribute of
  the same store** — a near-duplicate target for eval cases proposing a narrower isolation-focused
  variant of the same capability.
- `componentFixtureReasoningCore` — the agent's core reasoning and planning loop, which processes
  inputs and produces a sequence of actions. It selects and sequences actions; it does not itself
  gate or authorize their execution.
- `componentFixtureOrchestrationGateway` — the dispatch layer that receives the reasoning core's
  chosen actions and routes them onward to the tool-invocation surface, validating and normalizing
  inbound data before it reaches that surface. **Scoped to validation and normalization only** — it
  does not evaluate whether a specific action is authorized, only that the request is well-formed.
- `componentFixtureModelServingInfra` — the infrastructure that hosts and serves a trained model
  for inference, distinct from the model artifact itself.
- `componentFixtureTrainingDataStore` — the curated data fed into a model during training.

## Deliberate coverage gaps

The fixture is deliberately built so that no entry above covers either of the following loci,
grounding a "keep as new" verdict for eval cases proposing them:

- **Tool-hosting/serving infrastructure.** No entry represents the deployment/runtime substrate that
  hosts or serves a tool-integration surface. `componentFixtureToolInvocation` is scoped to the
  agent's *use* of already-available tools (including their discovery/registration), not the
  infrastructure that hosts and runs a tool server process; `componentFixtureModelServingInfra` is
  scoped to hosting a trained *model*, not a tool.
- **Action-authorization gating.** No entry represents a locus that makes or enforces an
  allow/deny decision on a specific requested action before it executes.
  `componentFixtureReasoningCore` selects and plans actions but does not gate their execution;
  `componentFixtureOrchestrationGateway` validates and normalizes the request but, per its own
  description above, explicitly does not evaluate authorization.

## Fixture edges

Only the edges a fixture-grounded case actually depends on are modeled; everything else is
deliberately left unspecified rather than invented:

- `componentFixtureReasoningCore.edges.to` includes `componentFixtureOrchestrationGateway`;
  `componentFixtureOrchestrationGateway.edges.from` includes `componentFixtureReasoningCore`. This
  is one of the fixture's two modeled direct edges, standing in for a "these two already talk
  directly" fact a case may need (e.g. testing in-line insertion of a new node between them).
- `componentFixtureOrchestrationGateway.edges.to` includes `componentFixtureToolInvocation`;
  `componentFixtureToolInvocation.edges.from` includes `componentFixtureOrchestrationGateway`.
- `componentFixtureToolInvocation.edges.to` and all edges of `componentFixtureMemoryStore`,
  `componentFixtureModelServingInfra`, and `componentFixtureTrainingDataStore` are not modeled by
  this fixture — no case currently needs them, and an unmodeled edge should not be read as "this
  component has no such edge in reality," only as "no fixture-grounded case depends on it."

## Fixture category/subcategory taxonomy

A pinned stand-in for the category/subcategory validity shape a case may need to check a placement
against, mirroring the real schema's `if`/`then` structure without depending on the live schema
file:

| Category | Valid subcategories |
|---|---|
| `componentsInfrastructure` | `componentsData`, `componentsModelDeployment` ("Model deployment components") |
| `componentsModel` | `componentsModelTraining`, `componentsModelCore`, `componentsOrchestration` |
| `componentsApplication` | `componentsAgent`, `componentsApplicationCore` |

A category/subcategory pairing not listed in this table is invalid under this fixture's pinned
taxonomy, independent of whatever the live `risk-map/schemas/components.schema.json` currently
enumerates.
