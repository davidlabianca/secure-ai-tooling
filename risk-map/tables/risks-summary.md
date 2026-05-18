| ID                                       | Title                                    | Description                                                                                                                                                                                                                                                                                                     | Category                         |
|:-----------------------------------------|:-----------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:---------------------------------|
| riskAcceleratorAndSystemSideChannels     | Accelerator and System Side-channels     | Cross-tenant leakage via hardware side-channels in CPUs, GPUs, TPUs, memory systems, and interconnects. These vulnerabilities exploit timing, cache, speculative execution, and memory access patterns to compromise data confidentiality and infer sensitive information in shared computing environments.<br> | risksDeploymentAndInfrastructure |
| riskAdapterPEFTInjection                 | Adapter/PEFT Injection                   | Trojaned adapters merged at runtime to bypass safety or exfiltrate data. Adapter/PEFT Injection can compromise model behavior and enable unauthorized access to sensitive information or system resources.<br>                                                                                                  | risksDeploymentAndInfrastructure |
| riskAgentDelegationChainOpacity          | Agent Delegation Chain Opacity           | Multi-hop agent delegation chains become opaque when intermediate agents do not emit structured delegation events, making it impossible to determine which human, agent, or system authorized or performed an action — even when individual authentication steps succeed.<br>                                   | risksDeploymentAndInfrastructure |
| riskAgenticDelegationConfusedDeputy      | Agentic Delegation Confused Deputy       | A high-privilege agent acts on behalf of a less-privileged caller without validating the caller's authorization at the delegation boundary, allowing the caller to escalate privileges through the deputy's own permissions.<br>                                                                                | risksDeploymentAndInfrastructure |
| riskCovertChannelsInModelOutputs         | Covert Channels in Model Outputs         | Hidden information transmission through model outputs or behavior patterns. Covert Channels in Model Outputs can enable unauthorized data exfiltration and steganographic communication bypassing security controls.<br>                                                                                        | risksRuntimeOutputSecurity       |
| riskCrossTenantCredentialPropagation     | Cross-Tenant Credential Propagation      | Shared or insufficiently tenant-scoped agent credentials allow a compromise in one tenant to propagate access across tenant boundaries through the identity layer.<br>                                                                                                                                          | risksDeploymentAndInfrastructure |
| riskDataPoisoning                        | Data Poisoning                           | Altering data sources used to train the model. In terms of impact, Data Poisoning is comparable to modifying the logic of an application to change its behavior.<br>                                                                                                                                            | risksSupplyChainAndDevelopment   |
| riskDenialOfMLService                    | Denial of ML Service                     | Overloading ML systems with resource-intensive queries. Like traditional DoS attacks, Denial of ML Service can reduce availability of or entirely disrupt a service.<br>                                                                                                                                        | risksRuntimeInputSecurity        |
| riskEconomicDenialOfWallet               | Economic Denial of Wallet                | Cost abuse via token inflation, long context, or tool loops that spike spend. Economic Denial of Wallet can lead to unexpected financial losses and service disruption through resource exhaustion attacks.<br>                                                                                                 | risksRuntimeInputSecurity        |
| riskEvaluationBenchmarkManipulation      | Evaluation/Benchmark Manipulation        | Poisoned or leaked evaluation sets misleading safety and robustness signals. Evaluation/Benchmark Manipulation can compromise model assessment accuracy and lead to deployment of unsafe or unreliable AI systems.<br>                                                                                          | risksRuntimeDataSecurity         |
| riskExcessiveDataHandling                | Excessive Data Handling                  | Using data for model training and development that exceeds authorized or legal boundaries for collection, retention, or processing. This may lead to policy and legal challenges.<br>                                                                                                                           | risksSupplyChainAndDevelopment   |
| riskExcessiveDataHandlingDuringInference | Excessive Data Handling During Inference | Unauthorized collection, retention, processing, or sharing of user data during model inference. This can lead to privacy violations and legal challenges.<br>                                                                                                                                                   | risksRuntimeDataSecurity         |
| riskFederatedDistributedTrainingPrivacy  | Federated/Distributed Training Privacy   | Gradient leakage and inversion attacks from untrusted clients in federated learning. Federated/Distributed Training Privacy risks can expose sensitive training data and compromise participant privacy.<br>                                                                                                    | risksSupplyChainAndDevelopment   |
| riskInferredSensitiveData                | Inferred Sensitive Data                  | Model inferring personal information not contained in training data or inputs. Inferred Sensitive Data may be considered a data privacy incident.<br>                                                                                                                                                           | risksRuntimeDataSecurity         |
| riskInsecureIntegratedComponent          | Insecure Integrated Component            | Software vulnerabilities that can be leveraged to compromise AI models. Insecure Integrated Component can lead to privacy and security concerns, as well as potential ethical and legal challenges.<br>                                                                                                         | risksDeploymentAndInfrastructure |
| riskInsecureModelOutput                  | Insecure Model Output                    | Unvalidated model output passed to the end user. Insecure Model Output poses risks to organizational reputation, security, and user safety.<br>                                                                                                                                                                 | risksRuntimeOutputSecurity       |
| riskMCPTransportHijacking                | MCP Transport Hijacking                  | Transport-layer attacks on MCP connections — including man-in-the-middle, session hijacking, DNS rebinding, and replay — intercept or modify agent-to-tool communication because the MCP specification does not mandate transport encryption or mutual authentication.<br>                                      | risksDeploymentAndInfrastructure |
| riskMaliciousLoaderDeserialization       | Malicious Loader/Deserialization         | Unsafe loaders for models and tokenizers that can cause remote code execution or integrity compromise. Malicious Loader/Deserialization poses significant security risks including system compromise and data breaches.<br>                                                                                     | risksSupplyChainAndDevelopment   |
| riskModelDeploymentTampering             | Model Deployment Tampering               | Unauthorized changes to model deployment components. Model Deployment Tampering can result in changes to model behavior.<br>                                                                                                                                                                                    | risksDeploymentAndInfrastructure |
| riskModelEvasion                         | Model Evasion                            | Changes to a prompt input to cause the model to produce incorrect inferences. Model Evasion can lead to reputational, legal, security, and privacy risks.<br>                                                                                                                                                   | risksRuntimeInputSecurity        |
| riskModelExfiltration                    | Model Exfiltration                       | Theft of a model. Similar to stealing code, this threat has both intellectual property and security implications.<br>                                                                                                                                                                                           | risksDeploymentAndInfrastructure |
| riskModelReverseEngineering              | Model Reverse Engineering                | Recreating a model by analyzing its inputs, outputs, and behaviors. A reverse engineer model can be used to create imitation products or adversarial attacks.<br>                                                                                                                                               | risksDeploymentAndInfrastructure |
| riskModelSourceTampering                 | Model Source Tampering                   | Tampering with the model's code or data. Model Source Tampering is similar to tampering with traditional software code, and can create vulnerabilities or unintended behavior.<br>                                                                                                                              | risksSupplyChainAndDevelopment   |
| riskOrchestratorRouteHijacking           | Orchestrator/Route Hijack                | Silent model or route swaps via configuration tampering or prompt-based routing abuse. Orchestrator/Route Hijack can redirect requests to malicious models or compromise routing integrity in AI systems.<br>                                                                                                   | risksRuntimeOutputSecurity       |
| riskPromptInjection                      | Prompt Injection                         | Tricking a model to run unintended commands. In terms of impact, Prompt Injection can change a model's behavior.<br>                                                                                                                                                                                            | risksRuntimeInputSecurity        |
| riskPromptResponseCachePoisoning         | Prompt/Response Cache Poisoning          | Cross-user contamination via shared LLM caches lacking isolation and validation. Prompt/Response Cache Poisoning can lead to information leakage, misinformation propagation, and unauthorized access to cached content.<br>                                                                                    | risksRuntimeDataSecurity         |
| riskRetrievalVectorStorePoisoning        | Retrieval/Vector Store Poisoning         | Poisoning retrieval corpora or vector indices to steer RAG outputs. Retrieval/Vector Store Poisoning can compromise the integrity of knowledge retrieval systems and lead to misinformation or malicious content injection.<br>                                                                                 | risksRuntimeOutputSecurity       |
| riskRogueActions                         | Rogue Actions                            | Unintended or manipulated model-based actions executed via extensions. Rogue Actions can cascade across systems with severe impact on organizational reputation, user trust, security, and safety.<br>                                                                                                          | risksRuntimeOutputSecurity       |
| riskRunawayAgentToolLoops                | Runaway Agent Tool Loops                 | Agents enter uncontrolled recursive tool-calling cycles at the orchestration layer, exhausting context windows, compute resources, and API budgets through emergent autonomous behavior or adversarial trigger.<br>                                                                                             | risksRuntimeInputSecurity        |
| riskSensitiveDataDisclosure              | Sensitive Data Disclosure                | Disclosure of sensitive data by the model. Sensitive Data Disclosure poses a threat to user privacy, organizational reputation, and intellectual property.<br>                                                                                                                                                  | risksRuntimeDataSecurity         |
| riskShadowAndUnknownAgents               | Shadow and Unknown Agents                | Unregistered agents operate with inherited or valid credentials outside identity lifecycle controls, creating persistent blind spots in agentic systems.<br>                                                                                                                                                    | risksDeploymentAndInfrastructure |
| riskStaleAgentIdentityBinding            | Stale Agent Identity Binding             | Agent identity credentials persist unchanged after the underlying model artifact is replaced, allowing a substituted model to operate with the original agent's full permissions because no cryptographic binding ties identity to a specific model version.<br>                                                | risksDeploymentAndInfrastructure |
| riskToolRegistryTampering                | Tool Registry Tampering                  | Compromise of previously vetted tool registries, MCP server manifests, or tool metadata, causing agents to select and invoke unintended tools through altered descriptions, schemas, or shadowed tool names.<br>                                                                                                | risksDeploymentAndInfrastructure |
| riskToolSourceProvenance                 | Tool Source Provenance                   | Use of unvetted or unverified tool registries, MCP server manifests, or tool metadata sources that may provide agents with deceptive tool descriptions, altered schemas, or shadowed tool names.<br>                                                                                                            | risksSupplyChainAndDevelopment   |
| riskUnauthorizedTrainingData             | Unauthorized Training Data               | Using unauthorized data for model training. Using a model trained with Unauthorized Training Data might lead to legal or ethical challenges.<br>                                                                                                                                                                | risksSupplyChainAndDevelopment   |
| riskZombieShadowMCPServers               | Zombie / Shadow MCP Servers              | Decommissioned or unregistered MCP servers remain accessible and respond to agent tool calls, allowing attackers to intercept or redirect legitimate requests.<br>                                                                                                                                              | risksDeploymentAndInfrastructure |

## References for riskAcceleratorAndSystemSideChannels
- [Hermes Attack: Steal DNN Models with Lossless Inference Accuracy](https://arxiv.org/abs/2006.12784) (paper)
- [I Know What You Said: Unveiling Hardware Cache Side-Channels in Local Large Language Model Inference](https://arxiv.org/abs/2505.06738) (paper)


## References for riskAdapterPEFTInjection
- [LoRATK: LoRA Once, Backdoor Everywhere in the Share-and-Play Ecosystem](https://arxiv.org/abs/2403.00108) (paper)
- [PETA: Parameter-Efficient Trojan Attacks](https://arxiv.org/abs/2310.00648) (paper)


## References for riskAgentDelegationChainOpacity
- [When AI Agents Go Rogue: Agent Session Smuggling Attack in A2A Systems](https://unit42.paloaltonetworks.com/agent-session-smuggling-in-agent2agent-systems/) (paper)


## References for riskAgenticDelegationConfusedDeputy
- [AWS IAM User Guide: The confused deputy problem](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html) (spec)
- [Supabase MCP can leak your entire SQL database](https://generalanalysis.com/blog/supabase-mcp-blog) (paper)
- [WhatsApp MCP Exploited: Exfiltrating your message history via MCP](https://invariantlabs.ai/blog/whatsapp-mcp-exploited) (paper)


## References for riskCovertChannelsInModelOutputs
- [Hidden in Plain Text: Emergence and Mitigation of Steganographic Collusion in LLMs](https://arxiv.org/abs/2410.03768) (paper)
- [Remote Timing Attacks on Efficient Language Model Inference](https://arxiv.org/abs/2410.17175) (paper)


## References for riskCrossTenantCredentialPropagation
- [Asana warns MCP AI feature exposed customer data to other orgs](https://www.bleepingcomputer.com/news/security/asana-warns-mcp-ai-feature-exposed-customer-data-to-other-orgs/) (news)
- [Salesforce OAuth Token Breach: What Every Security Team Must Know](https://www.valencesecurity.com/resources/blogs/salesforce-oauth-token-breach-what-every-security-team-must-know) (editorial)
- [BingBang: AAD misconfiguration led to Bing.com results manipulation and account takeover](https://www.wiz.io/blog/azure-active-directory-bing-misconfiguration) (paper)


## References for riskDataPoisoning
- [Poisoning Web-Scale Training Datasets is Practical](https://arxiv.org/abs/2302.10149) (paper)
- [Poisoning Language Models During Instruction Tuning](https://arxiv.org/abs/2305.00944) (paper)


## References for riskDenialOfMLService
- [Sponge Examples: Energy-Latency Attacks on Neural Networks](https://arxiv.org/abs/2006.03463) (paper)
- [Phantom Sponges: Exploiting Non-Maximum Suppression to Attack Deep Object Detectors](https://arxiv.org/abs/2205.13618) (paper)


## References for riskEconomicDenialOfWallet
- [Denial-of-Service Poisoning Attacks against Large Language Models](https://arxiv.org/abs/2410.10760) (paper)
- [ThinkTrap: Denial-of-Service Attacks against Black-box LLM Services via Infinite Thinking](https://arxiv.org/abs/2512.07086) (paper)


## References for riskEvaluationBenchmarkManipulation
- [Demonstrating specification gaming in reasoning models](https://arxiv.org/abs/2502.13295) (paper)
- [Selective Adversarial Attacks on LLM Benchmarks](https://arxiv.org/abs/2510.13570) (paper)


## References for riskExcessiveDataHandling
- [Clearview AI agrees to restrict use of face database](https://www.theguardian.com/us-news/2022/may/09/clearview-chicago-settlement-aclu) (news)


## References for riskExcessiveDataHandlingDuringInference
- [Samsung Bans ChatGPT Among Employees After Sensitive Code Leak](https://www.forbes.com/sites/siladityaray/2023/05/02/samsung-bans-chatgpt-and-other-chatbots-for-employees-after-sensitive-code-leak/) (news)


## References for riskFederatedDistributedTrainingPrivacy
- [Deep Leakage from Gradients](https://arxiv.org/abs/1906.08935) (paper)
- [FedMIA: An Effective Membership Inference Attack Exploiting All for One Principle in Federated Learning](https://arxiv.org/abs/2402.06289) (paper)


## References for riskInferredSensitiveData
- [Deep Neural Networks Are More Accurate Than Humans at Detecting Sexual Orientation From Facial Images](https://doi.org/10.1037/pspa0000098) (paper)
- [Automated Inference on Criminality using Face Images](https://arxiv.org/abs/1611.04135) (paper)


## References for riskInsecureIntegratedComponent
- [Security researchers expose new Alexa and Google Home vulnerability](https://www.theverge.com/2019/10/21/20924886/alexa-google-home-security-vulnerability-srlabs-phishing-eavesdropping) (news)
- [From Path Traversal to Supply Chain Compromise: Breaking MCP Server Hosting](https://blog.gitguardian.com/breaking-mcp-server-hosting/) (paper)


## References for riskInsecureModelOutput
- [AI hallucinates software packages and devs download them – even if potentially poisoned with malware](https://www.theregister.com/2024/03/28/ai_bots_hallucinate_software_packages/) (news)


## References for riskMCPTransportHijacking
- [Model Context Protocol specification (2025-11-25): Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) (spec)


## References for riskMaliciousLoaderDeserialization
- [Never a dill moment: Exploiting machine learning pickle files](https://blog.trailofbits.com/2021/03/15/never-a-dill-moment-exploiting-machine-learning-pickle-files/) (paper)
- [Weaponizing ML Models with Ransomware](https://hiddenlayer.com/research/weaponizing-machine-learning-models-with-ransomware/) (paper)
- [An Empirical Study on Remote Code Execution in Machine Learning Model Hosting Ecosystems](https://arxiv.org/abs/2601.14163) (paper)


## References for riskModelDeploymentTampering
- [Compromised PyTorch-nightly dependency chain between December 25th and December 30th, 2022](https://pytorch.org/blog/compromised-nightly-dependency/) (advisory)
- [Warning: PyTorch Models Vulnerable to Remote Code Execution via ShellTorch](https://thehackernews.com/2023/10/warning-pytorch-models-vulnerable-to.html) (news)
- [Hugging Face works with Wiz to strengthen AI cloud security](https://www.wiz.io/blog/wiz-and-hugging-face-address-risks-to-ai-infrastructure) (paper)


## References for riskModelEvasion
- [Slight Street Sign Modifications Can Completely Fool Machine Learning Algorithms](https://spectrum.ieee.org/slight-street-sign-modifications-can-fool-machine-learning-algorithms) (news)


## References for riskModelExfiltration
- [Meta's powerful AI language model has leaked online — what happens now?](https://www.theverge.com/2023/3/8/23629362/meta-ai-language-model-llama-leak-online-misuse) (news)


## References for riskModelReverseEngineering
- [Imitation Attacks and Defenses for Black-box Machine Translation Systems](https://arxiv.org/abs/2004.15015) (paper)
- [Alpaca: A Strong, Replicable Instruction-Following Model](https://crfm.stanford.edu/2023/03/13/alpaca.html) (paper)


## References for riskModelSourceTampering
- [Compromised PyTorch-nightly dependency chain between December 25th and December 30th, 2022](https://pytorch.org/blog/compromised-nightly-dependency/) (advisory)
- [Architectural Neural Backdoors from First Principles](https://arxiv.org/abs/2402.06957) (paper)


## References for riskOrchestratorRouteHijacking
- [CVE-2026-24779: Server-Side Request Forgery in vLLM MediaConnector](https://nvd.nist.gov/vuln/detail/CVE-2026-24779) (cve)
- [Rerouting LLM Routers](https://arxiv.org/abs/2501.01818) (paper)


## References for riskPromptInjection
- [Multi-modal prompt injection image attacks against GPT-4V](https://simonwillison.net/2023/Oct/14/multi-modal-prompt-injection/) (editorial)
- [Jailbroken: How Does LLM Safety Training Fail?](https://arxiv.org/abs/2307.02483) (paper)
- [Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection](https://arxiv.org/abs/2302.12173) (paper)


## References for riskPromptResponseCachePoisoning
- [From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching](https://arxiv.org/abs/2601.23088) (paper)
- [Shadow in the Cache: Unveiling and Mitigating Privacy Risks of KV-cache in LLM Inference](https://arxiv.org/abs/2508.09442) (paper)


## References for riskRetrievalVectorStorePoisoning
- [Poisoning Retrieval Corpora by Injecting Adversarial Passages](https://arxiv.org/abs/2310.19156) (paper)
- [Backdoor Attacks on Dense Retrieval via Public and Unintentional Triggers](https://arxiv.org/abs/2402.13532) (paper)


## References for riskRogueActions
- [Plugin Vulnerabilities: Visit a Website and Have Your Source Code Stolen](https://embracethered.com/blog/posts/2023/chatgpt-plugin-vulns-chat-with-code/) (editorial)
- [Supabase MCP can leak your entire SQL database](https://generalanalysis.com/blog/supabase-mcp-blog) (paper)


## References for riskRunawayAgentToolLoops
- [Microsoft AutoGen Issue #108: Infinite Loops with GPT-4](https://github.com/microsoft/autogen/issues/108) (editorial)


## References for riskSensitiveDataDisclosure
- [Preventing Verbatim Memorization in Language Models Gives a False Sense of Privacy](https://arxiv.org/abs/2210.17546) (paper)
- [Membership Inference Attacks against Machine Learning Models](https://arxiv.org/abs/1610.05820) (paper)


## References for riskShadowAndUnknownAgents
- [Gartner Identifies Critical GenAI Blind Spots That CIOs Must Urgently Address](https://www.gartner.com/en/newsroom/press-releases/2025-11-19-gartner-identifies-critical-genai-blind-spots-that-cios-must-urgently-address0) (editorial)


## References for riskStaleAgentIdentityBinding
- [Governing Dynamic Capabilities: Cryptographic Binding and Reproducibility Verification for AI Agent Tool Use](https://arxiv.org/abs/2603.14332) (paper)


## References for riskToolRegistryTampering
- [Model Context Protocol (MCP): A Security Overview](https://www.paloaltonetworks.com/blog/cloud-security/model-context-protocol-mcp-a-security-overview/) (editorial)
- [MCP Security Notification: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks) (paper)
- [From Path Traversal to Supply Chain Compromise: Breaking MCP Server Hosting](https://blog.gitguardian.com/breaking-mcp-server-hosting/) (paper)


## References for riskToolSourceProvenance
- [11 Emerging AI Security Risks with MCP (Model Context Protocol)](https://checkmarx.com/zero-post/11-emerging-ai-security-risks-with-mcp-model-context-protocol/) (editorial)
- [Attractive Metadata Attack: Inducing LLM Agents to Invoke Malicious Tools](https://arxiv.org/abs/2508.02110) (paper)


## References for riskUnauthorizedTrainingData
- [Spotify Takes Down Thousands of AI-Generated Tracks](https://aibusiness.com/ml/spotify-takes-down-thousands-of-ai-generated-tracks) (news)


## References for riskZombieShadowMCPServers
- [OWASP Web Security Testing Guide 4.2.10: Test for Subdomain Takeover](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/10-Test_for_Subdomain_Takeover) (spec)
