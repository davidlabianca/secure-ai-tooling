# Classical Security Lexicon (seed)

Canonical security terms of art for grounding CoSAI Risk Map terminology, with the invented/informal/product-specific terms each one replaces. NIST-first, then other standards and foundational literature.

This is a **living seed** — a stable snapshot (ADR-031 D4). Add entries as authoring surfaces them; each entry needs a canonical term and a source. Volatile framework identifiers are verified live, not pinned here.

## Access control and authorization

| Canonical term | Reground / catch these | Source |
|---|---|---|
| Policy Enforcement Point (PEP) | "agent control gateway", "guardrail proxy", "enforcement gateway", "AI firewall" (as a component identity) | NIST SP 800-207 (Zero Trust), SP 800-162 (ABAC) |
| Policy Decision Point (PDP) | "authorization brain", "decision engine" (when it means the PDP) | NIST SP 800-162 |
| Policy Information Point (PIP) | ad hoc "attribute lookup"/"context source" naming | NIST SP 800-162 |
| Policy Administration Point (PAP) | ad hoc "policy console"/"policy manager" naming | NIST SP 800-162 |
| Reference monitor | "central checker", "access gatekeeper" | Anderson 1972 (reference monitor concept); NIST glossary |
| Least privilege | "minimal permissions" is fine; catch invented framings that restate it | Saltzer & Schroeder 1975; NIST SP 800-53 AC-6 |
| Fail-safe defaults | invented framings for deny-by-default / default-deny access decisions | Saltzer & Schroeder 1975 (classical secure-design principle); NIST SP 800-53 AC-3 (access enforcement) |
| Confused deputy | novel names for delegated-authority abuse | Hardy 1988 |
| Separation of duties / privilege separation | "role splitting" | NIST SP 800-53 AC-5 |
| Identity provider (IdP) | "MCP authorization server" and other product-named identity planes → the role is the IdP | OAuth 2.0 / OIDC |

## Identity, tokens, transport

| Canonical term | Reground / catch these | Source |
|---|---|---|
| Mutual TLS (mTLS) / mutual authentication | "two-way secure channel" | RFC 8446, RFC 8705 |
| Token exchange | product-specific delegation-token naming | RFC 8693 |
| Dynamic client registration | product-specific "auto-enrollment" naming | RFC 7591 |
| Orphaned / unregistered principal; unauthorized asset | "zombie agents", "shadow agents", "ghost servers" | classical asset-management / IAM |
| Secrets / credential management | "secret sprawl", ad-hoc key handling, scattered API keys | CWE-522 (insufficiently protected credentials), CWE-798 (hard-coded credentials); NIST SP 800-57 (key management), SP 800-53 IA / SC families |

## Integrity, provenance, assurance

| Canonical term | Reground / catch these | Source |
|---|---|---|
| Attestation | "integrity proof", "trust receipt" | RFC 9334 (RATS); NIST |
| Provenance | "origin tracking" (when it means provenance) | SLSA; NIST SSDF (SP 800-218) |
| Defense in depth | "layered guardrails" (as a coined term) | NIST glossary |
| Trust boundary | "security edge", "control perimeter" (when it means a trust boundary) | threat-modeling canon; NIST |
| Audit logging / telemetry | "Agent Observability", "activity insight" | NIST SP 800-53 AU family |
| Input validation and sanitization | "Shield", "guardrail" (as a component/control identity for filtering/sanitizing input) → the role `input validation and sanitization` (corpus control `controlInputValidationAndSanitization`) | OWASP Input Validation Cheat Sheet; NIST SP 800-53 SI family (system and information integrity) |

## Generalization (role, not product/protocol)

The identity of a component/risk/control is the role or locus it occupies; a specific product or protocol is an attribute, not the name. Generalize and keep the product only as an example / external reference.

| Role-grain term | Generalize from | Note |
|---|---|---|
| Tool server / remote tool serving | "MCP server" | MCP is one instance; A2A, remote plugin hosts occupy the same role |
| Isolated / sandboxed execution | "MCP sandbox" | isolation locus is protocol-agnostic |
| Transport / session layer | "MCP transport", "JSON-RPC layer" | encoding is an attribute |
| External prompt template | "MCP prompts primitive" | provider-supplied instruction template; not a protocol taxonomy term |
| Tool / extension registry | "MCP package repository" | supply-chain role; ground in SLSA/SBOM/provenance |

## Human factors and usable security

| Canonical term | Reground / catch these | Source |
|---|---|---|
| Alert fatigue | "notification fatigue", "warning fatigue" | NIST SP 800-61 (incident handling); CISA / ENISA practitioner guidance |
| Habituation | desensitization to repeated security prompts; "prompt blindness" | usable-security literature (Bravo-Lillo et al.; Sunshine et al.); NIST SP 800-63B (authenticator UX) |
| Consent fatigue | reflexive approval of consent/confirmation dialogs | ENISA / GDPR (ICO) guidance — privacy-scoped |

> For AI-agent confirmation/consent surfaces specifically, these are the nearest established terms; where none fits cleanly, surface the non-US framing and flag to the maintainer (ADR-031 D3b) rather than coining.

## Non-US and international equivalents (D3b counterbalance)

When a term is contested or NIST is silent, surface the non-US framing so the choice is made against a broader base (ADR-031 D3b), and flag it for the maintainer. These are real, citable equivalents — use them to broaden, not to replace NIST-first.

| Concept | US framing | Non-US / international equivalent |
|---|---|---|
| AI risk management | NIST AI RMF | EU AI Act **Article 9** (risk management system); **ISO/IEC 23894** (AI risk management); **ISO/IEC 42001** (AI management system) |
| Human oversight | NIST AI RMF GOVERN; "human-in-the-loop" | EU AI Act **Article 14** (human oversight); "meaningful human control" (EU ethics/HLEG discourse — stronger emphasis than oversight) |
| Record-keeping / audit logging | NIST SP 800-53 AU family | EU AI Act **Article 12** (record-keeping / automatic event logging) |
| Data governance | NIST | EU AI Act **Article 10** (data and data governance) |
| Robustness / accuracy / security | NIST | EU AI Act **Article 15** (accuracy, robustness and cybersecurity) |
| Transparency | NIST | EU AI Act **Articles 13 & 50** (transparency obligations) |
| ML threat taxonomy | MITRE ATLAS | **ENISA** "Securing Machine Learning Algorithms" threat taxonomy |
| Secure AI development lifecycle | NIST SSDF (SP 800-218) | **UK NCSC + CISA** "Guidelines for Secure AI System Development" (2023); **ISO/IEC 42001** |
| AI concepts & terminology | NIST glossary | **ISO/IEC 22989** (AI concepts and terminology) |
| Alert / consent fatigue | NIST SP 800-61 / SP 800-63B | **ENISA** / GDPR (ICO) — consent fatigue (privacy-scoped) |

Note the convenient cases: EU AI Act Article 14 and NIST both say "human oversight," so the term is *not* contested there — do not manufacture a counterbalance flag when US and non-US bodies agree.

## Usage notes

- **NIST-first:** when more than one source offers a term, prefer NIST (ADR-031 D3a).
- **Contested / NIST-silent:** do not coin. Surface any non-US (ENISA/ISO) framing and flag to the maintainer (ADR-031 D3b).
- **Sources are required:** an entry without a real source is not lexicon material — it is a candidate for governance review, not a rule.
