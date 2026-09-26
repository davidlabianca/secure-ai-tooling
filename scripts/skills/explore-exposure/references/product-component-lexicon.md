# Product → Component Lexicon (seed)

Maps common products/technologies to the CoSAI Risk Map component(s) they **implement or protect**. A **living seed** — extend it as products come up. When a product is not listed, infer the nearest component from its role (optionally confirm via web lookup) and **flag the mapping as inferred**, not curated.

Most rows are **one-part**: the product implements or protects a single component (or a short, listed set). A handful of rows — isolation or hosting-boundary products, where the corpus places other workloads inside the boundary — are **two-part**: the product **implements** the boundary itself and **protects** the workloads that run inside it; the **exposure via (candidates)** column names those protected components, each cited to its ground. See "Usage notes" below.

Verify component ids against `risk-map/yaml/components.yaml` before relying on them — component ids evolve.

## Confidential / isolated compute infrastructure

Each of these implements `componentIsolationRuntime`, the confinement boundary (`risk-map/yaml/components.yaml`), and protects the workloads that run inside it — the exposure-via candidates: `componentModelServing`, `componentReasoningCore` and `componentApplication`, confined transitively because they are `componentRuntimeHosting`'s three hosted workloads (ADR-030 D13), and `componentToolServer`, on the weaker ground that `componentToolHosting`'s own description names it as what runs on that substrate (ADR-030 D9 types no ADR containment edge to it). `componentModelTrainingTuning` and `componentMemory` are covered by `controlIsolatedConfidentialComputing` (confidential training or memory workloads) but are **note-only** — the corpus does not place them inside the isolation boundary, so none of these products protects or implements them as a boundary workload. None of these products protects or implements `componentModelStorage`: an enclave has no persistent storage.

| Product / technology | Implements | Exposure via (candidates) | Note |
|---|---|---|---|
| AWS Nitro Enclaves | `componentIsolationRuntime` | `componentModelServing`, `componentReasoningCore`, `componentApplication`, `componentToolServer` | The AWS Nitro Enclaves concepts page states an enclave has no external network connectivity and no persistent storage — the ground for excluding `componentModelStorage` here and at every other row in this section. Note-only: `componentModelTrainingTuning`, `componentMemory` (covered by `controlIsolatedConfidentialComputing`). |
| Azure Confidential Computing | `componentIsolationRuntime` | `componentModelServing`, `componentReasoningCore`, `componentApplication`, `componentToolServer` | Confidential VMs and confidential containers are the same enclave/attestation shape as Nitro; which workload runs inside is a deployment choice. Note-only: `componentModelTrainingTuning`, `componentMemory` (covered by `controlIsolatedConfidentialComputing`). |
| GCP Confidential VMs | `componentIsolationRuntime` | `componentModelServing`, `componentReasoningCore`, `componentApplication`, `componentToolServer` | Confidential VMs' persistent disks are encryption at rest, not a confidential-computing property — the memory-encryption boundary is what confines the workload. Note-only: `componentModelTrainingTuning`, `componentMemory` (covered by `controlIsolatedConfidentialComputing`). |
| Intel SGX/TDX | `componentIsolationRuntime` | `componentModelServing`, `componentReasoningCore`, `componentApplication`, `componentToolServer` | Hardware enclave (SGX) / trust-domain (TDX) boundary; the running workload is a deployment choice, not a product property. Note-only: `componentModelTrainingTuning`, `componentMemory` (covered by `controlIsolatedConfidentialComputing`). |
| AMD SEV | `componentIsolationRuntime` | `componentModelServing`, `componentReasoningCore`, `componentApplication`, `componentToolServer` | Hardware VM memory-encryption boundary; the running workload is a deployment choice, not a product property. Note-only: `componentModelTrainingTuning`, `componentMemory` (covered by `controlIsolatedConfidentialComputing`). |
| Generic TEEs | `componentIsolationRuntime` | `componentModelServing`, `componentReasoningCore`, `componentApplication`, `componentToolServer` | Same boundary shape as the named products above; use this row when the specific TEE product isn't listed. Note-only: `componentModelTrainingTuning`, `componentMemory` (covered by `controlIsolatedConfidentialComputing`). |

## Model serving / inference

| Product / technology | Component(s) | Note |
|---|---|---|
| vLLM, TGI (Text Generation Inference), NVIDIA Triton, Ray Serve, SageMaker/Vertex/Bedrock endpoints, KServe | `componentModelServing` | The runtime that serves predictions |
| Hosted model APIs (third-party model providers) | `componentTheModel`, `componentModelServing` | The model + its serving surface (you consume it) |

## Model & data storage / registries

| Product / technology | Component(s) | Note |
|---|---|---|
| Hugging Face Hub | `componentModelRegistry`, `componentModelStorage` | Both roles: the registry is the catalog/discovery layer (`componentModelRegistry`'s own description names it as an example); it also hosts the artifact files themselves, one of the repository shapes `componentModelStorage`'s own description calls "model registry-backed storage" |
| MLflow Model Registry, model catalogs | `componentModelRegistry` | The registration and cataloging layer — metadata, model cards, provenance; not the artifact storage, which `componentModelRegistry`'s own description says is a separate, referenced locus |
| S3 / GCS / data lakes / feature stores (training data) | `componentDataStorage`, `componentTrainingData` | Training-data storage |

## Agent frameworks / orchestration

| Product / technology | Component(s) | Note |
|---|---|---|
| LangChain, LlamaIndex, Semantic Kernel, CrewAI, AutoGen, LangGraph | `componentReasoningCore`, `componentOrchestrationInputHandling`, `componentOrchestrationOutputHandling` | Agent reasoning + orchestration plumbing |
| MCP servers, tool servers, plugin hosts, remote tool endpoints | `componentToolServer` | The endpoint that hosts and exposes tool capabilities over a tooling protocol (MCP, A2A, remote plugin); distinct from the capabilities themselves (`componentTools`) |

## Retrieval / memory

| Product / technology | Component(s) | Note |
|---|---|---|
| Pinecone, Weaviate, Chroma, Milvus, pgvector (as a RAG corpus) | `componentRAGContent` | Retrieval-augmented content / vector store |
| Redis / a persistent agent memory store | `componentMemory` | Agent long-term/session memory |

## Input/output handling & guardrails

| Product / technology | Component(s) | Note |
|---|---|---|
| NeMo Guardrails, Llama Guard, prompt-filtering / content-moderation layers | `componentApplicationInputHandling`, `componentApplicationOutputHandling`, `componentAgentInputHandling`, `componentAgentOutputHandling` | Input/output validation loci (pick the layer that matches the deployment) |
| API gateways / auth proxies in front of AI services | `componentModelServing`, `componentApplicationNetworkPolicyEnforcementPoint`, `componentToolNetworkPolicyEnforcementPoint`, `componentAuthorizationPolicyEnforcementPoint` | Pick by what the gateway fronts: in front of a model-serving endpoint → componentModelServing (its own description: it enforces ingress itself); an application's egress gateway to a model endpoint → componentApplicationNetworkPolicyEnforcementPoint; a gateway in front of a tool server → componentToolNetworkPolicyEnforcementPoint (its own description: "a sidecar or gateway in front of componentToolServer"); per-invocation action authorization on the tool path → componentAuthorizationPolicyEnforcementPoint (its own description names "API-gateway authorization" as a realization) |

## Usage notes

- A product maps to the component(s) it **implements** (it *is* that locus) or **protects** (it secures that locus) — say which. For a two-part row, the product implements the boundary and protects the workloads named in *Exposure via (candidates)* — see the next bullet.
- **Exposure via (candidates)** is how a two-part row expresses **protects**: the product implements the boundary component and protects the workloads the corpus places inside it. The candidates *are* those protected components, each cited to its ground (an ADR containment edge or a component description) — never a data-flow inference the answer draws itself. Reserved for products whose implemented component is an isolation or hosting boundary that the corpus says other workloads run inside (the confidential-compute group above). Every other row in this lexicon is one-part: it names only the component(s) the product implements or protects directly.
- **Reverse lookup** (finding which curated row(s) name a given component): key it on the id(s) a row **implements**, never on a two-part row's exposure-via candidates. A candidate such as `componentModelServing` does not inherit the isolation-boundary row's exposure just because it is listed there as a candidate.
- Prefer the most specific component; a product may touch more than one.
- Not listed? Infer from role, confirm via web lookup if useful, and **flag the mapping as inferred**.
