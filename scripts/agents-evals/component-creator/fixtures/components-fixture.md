# Component corpus fixture

**This is test input, not CoSAI Risk Map content.** It is a small, hand-authored, purpose-built
stand-in for `risk-map/yaml/components.yaml`, used only to grade eval cases whose correct verdict
depends on "does an existing component already cover this candidate" — never the live, growing
corpus (see ADR-033 Amendment 2026-07-30, D7). It must not be cited, validated, or consumed as if
it were real Risk Map content. It is refreshed only if the component entity shape changes
structurally (e.g. a required schema field is added), never in response to the real corpus
growing.

Fixture entries:

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
  inputs and produces a sequence of actions.
- `componentFixtureModelServingInfra` — the infrastructure that hosts and serves a trained model
  for inference, distinct from the model artifact itself.
- `componentFixtureTrainingDataStore` — the curated data fed into a model during training.
