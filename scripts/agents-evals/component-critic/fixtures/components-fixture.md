# Component corpus fixture

**This is test input, not CoSAI Risk Map content.** It is a small, hand-authored, purpose-built
stand-in for `risk-map/yaml/components.yaml`, used only to grade eval cases whose correct verdict
depends on "does an existing component already cover this candidate" — never the live, growing
corpus (see ADR-033 Amendment 2026-07-30, D7). It must not be cited, validated, or consumed as if
it were real Risk Map content. It is refreshed only if the component entity shape changes
structurally (e.g. a required schema field is added), never in response to the real corpus
growing.

This fixture is independent of, and not required to match, the fixture shipped alongside
`component-creator`'s eval tree (`scripts/agents-evals/component-creator/fixtures/`) — each agent's
eval tree ships its own fixture (ADR-033 D8c), and the authors chose not to require the two to match
even where the underlying scenario is similar.

## Fixture entries

- `componentFixtureReasoningCore` — the agent's core reasoning and planning loop, which processes
  inputs and produces a sequence of actions. It selects and sequences actions; it does not itself
  gate or authorize their execution.
- `componentFixtureOrchestrationGateway` — the dispatch layer that receives the reasoning core's
  chosen actions and routes them onward to the tool-invocation surface, validating and normalizing
  inbound data before it reaches that surface. **Scoped to validation and normalization only** — it
  does not evaluate whether a specific action is authorized, only that the request is well-formed.
- `componentFixtureToolInvocation` — the external APIs, services, and third-party integrations an
  agent invokes to take action in the world. Scoped to the agent's use of already-available tools,
  not the infrastructure that hosts or serves them.
- `componentFixtureModelServingInfra` — the infrastructure that hosts and serves a trained model
  for inference, distinct from the model artifact itself and from any tool-serving infrastructure.
- `componentFixtureModelEvaluation` — the process that tests a trained model checkpoint's
  performance and behavior, during training and again after training completes, before the model is
  deployed or wired into any downstream system such as an agent. This is the testing *process*, not
  the data it reads.
- `componentFixtureTrainingDataStore` — the curated data fed into a model during training.

## Deliberate coverage gaps

- **Evaluation/benchmark data as an artifact.** No entry represents the held-out or benchmark
  dataset itself. `componentFixtureTrainingDataStore` is scoped to training data; `componentFixture-
  ModelEvaluation` is the process that reads a dataset, not the dataset artifact.
- **Deployed-agent behavioral testing.** No entry represents a system that runs recurring
  behavioral tests against an already-deployed agent (as opposed to `componentFixtureModel-
  Evaluation`'s training-time/pre-deployment scope).
- **Action-authorization gating.** No entry represents a locus that makes or enforces an
  allow/deny decision on a specific requested action before it executes.
  `componentFixtureReasoningCore` selects and plans actions but does not gate their execution;
  `componentFixtureOrchestrationGateway` validates and normalizes the request but, per its own
  description above, explicitly does not evaluate authorization.
- **Tool-hosting/serving infrastructure.** No entry represents the deployment/runtime substrate
  that hosts or serves a tool-integration surface, as distinct from `componentFixtureToolInvocation`
  (the agent's use of already-available tools) and `componentFixtureModelServingInfra` (hosting a
  trained model, not a tool).

## Fixture edges

Only the edges a fixture-grounded case actually depends on are modeled:

- `componentFixtureReasoningCore.edges.to` includes `componentFixtureOrchestrationGateway`;
  `componentFixtureOrchestrationGateway.edges.from` includes `componentFixtureReasoningCore`.
- `componentFixtureOrchestrationGateway.edges.to` includes `componentFixtureToolInvocation`;
  `componentFixtureToolInvocation.edges.from` includes `componentFixtureOrchestrationGateway`.
- `componentFixtureToolInvocation.edges.to` is not modeled in this fixture (a deliberately unmodeled
  terminal — no fixture-grounded case depends on anything downstream of it).
- All other edges (of `componentFixtureModelServingInfra`, `componentFixtureModelEvaluation`, and
  `componentFixtureTrainingDataStore`) are not modeled — no case currently needs them, and an
  unmodeled edge should not be read as "this component has no such edge in reality," only as "no
  fixture-grounded case depends on it."
