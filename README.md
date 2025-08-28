# **Coalition for Secure AI (CoSAI) Tooling**

This repository is for the work of the **Coalition for Secure AI (CoSAI)**. CoSAI is an [OASIS Open Project](https://www.oasis-open.org/open-projects/) and an open ecosystem of AI and security experts from industry-leading organizations. We are dedicated to sharing best practices for secure AI deployment and collaborating on AI security research and tool development.

For more information on CoSAI, please visit the [CoSAI website](https://www.oasis-open.org/projects/cosai/) and the [Open Project repository](https://github.com/oasis-open/cosai), which contains our governance information and project charter.

---

## **Projects**

This repository contains tools, frameworks, and resources developed by the CoSAI community.

### **Coalition for Secure AI Risk Map (CoSAI-RM)**

The **CoSAI Risk Map** is a framework for identifying, analyzing, and mitigating security risks in Artificial Intelligence systems. As traditional software security practices are not always sufficient for AI, this project provides a shared understanding and a common language for addressing the unique security challenges of the AI development lifecycle.

The goal is to provide a structured map of the AI security landscape, helping practitioners understand how components connect and where risks might arise. It addresses several foundational industry challenges:

* **A common language:** It establishes a shared vocabulary for AI risks to reduce confusion and enable consistent tracking and mitigation of threats.  
* **A clear picture:** It provides a holistic framework that identifies risks throughout the entire system—including data pipelines, infrastructure, and deployment—not just within the isolated model.  
* **Focus beyond the model:** It counters the overemphasis on model-centric threats by mapping risks across the broader AI ecosystem.

#### **How It Works**

The Risk Map organizes the AI development lifecycle into four primary groups: **Data, Infrastructure, Model,** and **Application**. The framework itself is broken down into four key areas:

* **Components**: The fundamental building blocks of an AI system.  
* **Risks**: A catalog of potential security threats, such as Data Poisoning or Model Evasion.  
* **Controls**: The security measures that can mitigate these risks.  
* **Personas**: The key roles involved, namely the Model Creator and the Model Consumer.

The framework is provided as a set of human-readable .yaml files and machine-readable .schema.json files that you can use to learn, assess your own projects, and build upon for your organization's needs.

[Explore the full CoSAI Risk Map project here...](./risk-map/)