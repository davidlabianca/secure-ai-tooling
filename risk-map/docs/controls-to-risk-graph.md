```mermaid
---
config:
  layout: elk
  elk:
    mergeEdges: True
    nodePlacementStrategy: NETWORK_SIMPLEX
---

graph LR
   %%{init: {'flowchart': {'nodeSpacing': 30, 'rankSpacing': 40, 'padding': 5, 'wrappingWidth': 250}}}%%
    classDef hidden display: none;
    classDef allControl stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5

    subgraph risks
    subgraph risksSupplyChainAndDevelopment ["Supply Chain And Development Risks"]
        DP[Data Poisoning]
        EDH[Excessive Data Handling]
        MST[Model Source Tampering]
        UTD[Unauthorized Training Data]
    end

    subgraph risksDeploymentAndInfrastructure ["Deployment And Infrastructure Risks"]
        IIC[Insecure Integrated Component]
        MDT[Model Deployment Tampering]
        MRE[Model Reverse Engineering]
        MXF[Model Exfiltration]
    end

    subgraph risksRuntimeInputSecurity ["Runtime Input Security Risks"]
        DMS[Denial of ML Service]
        MEV[Model Evasion]
        PIJ[Prompt Injection]
    end

    subgraph risksRuntimeDataSecurity ["Runtime Data Security Risks"]
        ISD[Inferred Sensitive Data]
        SDD[Sensitive Data Disclosure]
    end

    subgraph risksRuntimeOutputSecurity ["Runtime Output Security Risks"]
        IMO[Insecure Model Output]
        RA[Rogue Actions]
    end

    end

    subgraph controls
    subgraph controlsData ["Data Controls"]
        controlPrivacyEnhancingTechnologies[Privacy Enhancing Technologies]
        controlTrainingDataManagement[Training Data Management]
        controlTrainingDataSanitization[Training Data Sanitization]
        controlUserDataManagement[User Data Management]
    end

    subgraph controlsInfrastructure ["Infrastructure Controls"]
        controlModelAndDataAccessControls[Model and Data Access Controls]
        controlModelAndDataIntegrityManagement[Model and Data Integrity Management]
        controlModelAndDataInventoryManagement[Model and Data Inventory Management]
        controlSecureByDefaultMLTooling[Secure-by-Default ML Tooling]
    end

    subgraph controlsModel ["Model Controls"]
        controlAdversarialTrainingAndTesting[Adversarial Training and Testing]
        controlInputValidationAndSanitization[Input Validation and Sanitization]
        controlOutputValidationAndSanitization[Output Validation and Sanitization]
    end

    subgraph controlsApplication ["Application Controls"]
        controlAgentObservability[Agent Observability]
        controlAgentPluginPermissions[Agent Permissions]
        controlAgentPluginUserControl[Agent User Control]
        controlApplicationAccessManagement[Application Access Management]
        controlUserTransparencyAndControls[User Transparency and Controls]
    end

    subgraph controlsAssurance ["Assurance Controls"]
        controlIncidentResponseManagement[Incident Response Management]
        controlRedTeaming[Red Teaming]
        controlThreatDetection[Threat Detection]
        controlVulnerabilityManagement[Vulnerability Management]
    end

    subgraph controlsGovernance ["Governance Controls"]
        direction LR
        controlInternalPoliciesAndEducation[Internal Policies and Education]
        controlProductGovernance[Product Governance]
        controlRiskGovernance[Risk Governance]
        controlUserPoliciesAndEducation[User Policies and Education]
    end

    end

    subgraph components
    subgraph componentsInfrastructure ["Infrastructure Components"]
        componentDataFilteringAndProcessing[Data Filtering and Processing]
        componentDataSources[Data Sources]
        componentDataStorage[Data Storage Infrastructure]
        componentTrainingData[Training Data]
        subgraph componentsModels ["Models"]
            componentModelServing[Model Serving Infrastructure]
            componentModelStorage[Model Storage]
        end
    end

    subgraph componentsModel ["Model Components"]
        componentMemory[Model Memory]
        componentModelFrameworksAndCode[Model Frameworks and Code]
        componentOrchestrationInputHandling[Input Handling]
        componentOrchestrationOutputHandling[Output Handling]
        componentRAGContent[Retrieval Augmented Generation & Content]
        componentTheModel[The Model]
        componentTools[External Tools and Services]
        subgraph componentsModelSubgroup ["Model Subgroup"]
            componentModelEvaluation[Model Evaluation]
            componentModelTrainingTuning[Training and Tuning]
        end
    end

    subgraph componentsApplication ["Application Components"]
        componentAgentInputHandling[Input Handling]
        componentAgentOutputHandling[Output Handling]
        componentAgentSystemInstruction[Agent System Instructions]
        componentAgentUserQuery[Agent User Query]
        componentApplication[Application]
        componentApplicationInputHandling[Input Handling]
        componentApplicationOutputHandling[Output Handling]
        componentReasoningCore[Agent Reasoning Core]
    end

    end

    %% Risk to Control relationships
    DP --> controlModelAndDataAccessControls
    DP --> controlModelAndDataIntegrityManagement
    DP --> controlModelAndDataInventoryManagement
    DP --> controlSecureByDefaultMLTooling
    DP --> controlTrainingDataSanitization
    UTD --> controlTrainingDataManagement
    UTD --> controlTrainingDataSanitization
    MST --> controlModelAndDataAccessControls
    MST --> controlModelAndDataIntegrityManagement
    MST --> controlModelAndDataInventoryManagement
    MST --> controlSecureByDefaultMLTooling
    EDH --> controlUserDataManagement
    EDH --> controlUserTransparencyAndControls
    MXF --> controlModelAndDataAccessControls
    MXF --> controlModelAndDataInventoryManagement
    MXF --> controlSecureByDefaultMLTooling
    MDT --> controlSecureByDefaultMLTooling
    DMS --> controlApplicationAccessManagement
    MRE --> controlApplicationAccessManagement
    IIC --> controlAgentPluginPermissions
    IIC --> controlUserPoliciesAndEducation
    PIJ --> controlAdversarialTrainingAndTesting
    PIJ --> controlInputValidationAndSanitization
    PIJ --> controlOutputValidationAndSanitization
    MEV --> controlAdversarialTrainingAndTesting
    SDD --> controlAdversarialTrainingAndTesting
    SDD --> controlAgentObservability
    SDD --> controlAgentPluginPermissions
    SDD --> controlAgentPluginUserControl
    SDD --> controlOutputValidationAndSanitization
    SDD --> controlPrivacyEnhancingTechnologies
    SDD --> controlUserDataManagement
    SDD --> controlUserPoliciesAndEducation
    SDD --> controlUserTransparencyAndControls
    ISD --> controlAdversarialTrainingAndTesting
    ISD --> controlOutputValidationAndSanitization
    ISD --> controlTrainingDataManagement
    IMO --> controlAdversarialTrainingAndTesting
    IMO --> controlOutputValidationAndSanitization
    RA --> controlAgentObservability
    RA --> controlAgentPluginPermissions
    RA --> controlAgentPluginUserControl
    RA --> controlOutputValidationAndSanitization

    %% Control to Component relationships (reused from ControlGraph)
    controlPrivacyEnhancingTechnologies --> componentsModelSubgroup
    controlTrainingDataManagement --> componentDataSources
    controlTrainingDataManagement --> componentTrainingData
    controlTrainingDataManagement --> componentsModelSubgroup
    controlTrainingDataSanitization --> componentDataFilteringAndProcessing
    controlUserDataManagement --> componentDataStorage
    controlModelAndDataInventoryManagement --> componentsModelSubgroup
    controlModelAndDataInventoryManagement --> componentsModels
    controlModelAndDataAccessControls --> componentsModelSubgroup
    controlModelAndDataAccessControls --> componentsModels
    controlModelAndDataIntegrityManagement --> componentsModelSubgroup
    controlModelAndDataIntegrityManagement --> componentsModels
    controlSecureByDefaultMLTooling --> componentsModelSubgroup
    controlSecureByDefaultMLTooling --> componentsModels
    controlInputValidationAndSanitization --> componentAgentInputHandling
    controlInputValidationAndSanitization --> componentOrchestrationInputHandling
    controlOutputValidationAndSanitization --> componentAgentOutputHandling
    controlOutputValidationAndSanitization --> componentOrchestrationOutputHandling
    controlAdversarialTrainingAndTesting --> componentTheModel
    controlApplicationAccessManagement --> componentApplication
    controlUserTransparencyAndControls --> componentApplication
    controlAgentPluginUserControl --> componentReasoningCore
    controlAgentPluginPermissions --> componentMemory
    controlAgentPluginPermissions --> componentRAGContent
    controlAgentPluginPermissions --> componentReasoningCore
    controlAgentPluginPermissions --> componentTools
    controlRedTeaming -.-> components
    controlVulnerabilityManagement -.-> components
    controlThreatDetection -.-> components
    controlIncidentResponseManagement -.-> components
    controlAgentObservability --> componentAgentInputHandling
    controlAgentObservability --> componentAgentOutputHandling
    controlAgentObservability --> componentOrchestrationInputHandling
    controlAgentObservability --> componentOrchestrationOutputHandling
    controlAgentObservability --> componentReasoningCore

    %% Edge styling
    linkStyle 0,4,8,12,16,20,24,28,32,36,40 stroke:#e6cbce,stroke-width:2px,stroke-dasharray: 5 3
    linkStyle 1,5,9,13,17,21,25,29,33,37,41 stroke:#b66871,stroke-width:2px,stroke-dasharray: 8 4
    linkStyle 2,6,10,14,18,22,26,30,34,38,42 stroke:#b66871,stroke-width:2px,stroke-dasharray: 10 2
    linkStyle 3,7,11,15,19,23,27,31,35,39 stroke:#1c0d0f,stroke-width:2px,stroke-dasharray: 12 5

%% Node style definitions
    style risksSupplyChainAndDevelopment fill:#ffeef0,stroke:#e91e63,stroke-width:2px
    style risksDeploymentAndInfrastructure fill:#ffeef0,stroke:#e91e63,stroke-width:2px
    style risksRuntimeInputSecurity fill:#ffeef0,stroke:#e91e63,stroke-width:2px
    style risksRuntimeDataSecurity fill:#ffeef0,stroke:#e91e63,stroke-width:2px
    style risksRuntimeOutputSecurity fill:#ffeef0,stroke:#e91e63,stroke-width:2px
    style components fill:#f0f0f0,stroke:#666666,stroke-width:3px,stroke-dasharray: 10 5
    style controls fill:#f0f0f0,stroke:#666666,stroke-width:3px,stroke-dasharray: 10 5
    style risks fill:#f0f0f0,stroke:#666666,stroke-width:3px,stroke-dasharray: 10 5
    style componentsInfrastructure fill:#e6f3e6,stroke:#333333,stroke-width:2px
    style componentsApplication fill:#e6f0ff,stroke:#333333,stroke-width:2px
    style componentsModel fill:#ffe6e6,stroke:#333333,stroke-width:2px
```
