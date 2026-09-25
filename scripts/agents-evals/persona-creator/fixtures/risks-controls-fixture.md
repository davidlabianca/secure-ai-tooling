# Risk and control corpus fixture

**This is test input, not CoSAI Risk Map content.** It is a small, hand-authored, purpose-built
stand-in for `risk-map/yaml/risks.yaml` and `risk-map/yaml/controls.yaml`. It must not be cited,
validated, or consumed as if it were real Risk Map content. It is refreshed only if the risk or
control entity shape changes structurally, never in response to the real corpus growing.

The five entries below are the complete set of risks and controls for any case that names this file.
Persona and component ids are the real active ids.

```yaml
id: controlSyntheticHardwareIsolatedExecution
title: Hardware-Isolated Execution
description:
  - >
    Use technologies that minimize the risk of third-party access to workloads via
    hardware-enforced isolation, such as trusted execution environments and secure enclaves.
category: controlsInfrastructure
personas:
  - personaPlatformProvider
  - personaModelServing
  - personaAgenticProvider
  - personaApplicationDeveloper
components:
  - componentModelServing
  - componentModelTrainingTuning
risks:
  - riskSyntheticAcceleratorSideChannels
```

```yaml
id: controlSyntheticSecureByDefaultComponents
title: Secure-by-Default Components
description:
  - >
    Use secure-by-default frameworks, libraries, software systems, and hardware components.
category: controlsInfrastructure
personas:
  - personaPlatformProvider
  - personaModelServing
  - personaAgenticProvider
  - personaApplicationDeveloper
components:
  - componentModelServing
  - componentModelTrainingTuning
risks:
  - riskSyntheticAcceleratorSideChannels
```

```yaml
id: controlSyntheticModelArtifactSigning
title: Model Artifact Signing
description:
  - >
    Sign model artifacts at release and verify the signature before a model is loaded for
    serving or fine-tuning.
category: controlsModel
personas:
  - personaModelProvider
  - personaModelServing
components:
  - componentModelStorage
  - componentModelServing
risks:
  - riskSyntheticModelArtifactTampering
```

```yaml
id: riskSyntheticAcceleratorSideChannels
title: Accelerator Side-Channels
shortDescription:
  - >
    Cross-tenant leakage through timing, cache, and memory-access side-channels in shared GPUs,
    TPUs, and other accelerators, exposing another tenant's model weights, training data, or keys.
longDescription:
  - >
    Mitigations are applied where the workload runs: dedicated instances, hardware partitioning,
    cache partitioning, disabling simultaneous multithreading, secure scheduling, and noise
    injection.
category: risksDeploymentAndInfrastructure
personas:
  - personaPlatformProvider
  - personaModelServing
  - personaApplicationDeveloper
  - personaEndUser
controls:
  - controlSyntheticHardwareIsolatedExecution
  - controlSyntheticSecureByDefaultComponents
```

```yaml
id: riskSyntheticModelArtifactTampering
title: Model Artifact Tampering
shortDescription:
  - >
    An attacker modifies a model artifact between its release and its loading, so the model that
    runs is not the model that was published.
longDescription:
  - >
    Mitigations verify the artifact at load time: signature checks against the publisher's key and
    integrity checks on the stored artifact.
category: risksSupplyChainAndDevelopment
personas:
  - personaModelProvider
  - personaModelServing
controls:
  - controlSyntheticModelArtifactSigning
```
