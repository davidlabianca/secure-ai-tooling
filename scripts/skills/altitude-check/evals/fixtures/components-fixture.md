# Component placement fixture

**This is test input, not CoSAI Risk Map content.** It is a small, hand-authored, purpose-built
stand-in for `risk-map/yaml/components.yaml`, used only to grade eval cases whose correct verdict
depends on "does anything already cover this candidate" — never the live, growing corpus (see
ADR-033 Amendment 2026-07-30, D7). It must not be cited, validated, or consumed as if it were real
Risk Map content. It is refreshed only if the component entity shape changes structurally (e.g. a
required schema field is added), never in response to the real corpus growing.

Fixture entries:

- `componentAgentReasoningCore` — the agent's core reasoning/decision loop.
- `componentAgentInputHandling` — validates and normalizes input format/structure (encoding,
  schema, length) reaching the reasoning core; does not perform semantic or adversarial-content
  analysis.
- `componentTools` — external tools and services the agent invokes.
- `componentRAGContent` — the retrieval-augmented-generation content store.
- `componentModelServing` — the runtime that serves the model for inference.
- `componentTrainingData` — data used to train or fine-tune the model.
- `componentEvalHarnessAndReporting` — benchmark selection, running evals, scoring, and
  generating the human-facing report, all in one node. **Deliberately over-broad** — three
  distinct loci (selection, execution, reporting) bundled together, a C3 "not
  reader-instructive at this grain" failure that should decompose, not merely adjust.
