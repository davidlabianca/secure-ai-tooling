# Identification Questions Style Guide

This guide covers how to write `identificationQuestions` for personas in `risk-map/yaml/personas.yaml`. Identification questions help readers determine whether a given persona applies to them based on what they do, not what their job title is.

---

## Purpose

Identification questions serve two functions:

1. **Self-selection** — Readers scan these questions to determine which persona(s) describe their activities and, by extension, which risks and controls apply to them.
2. **Boundary clarification** — Questions prevent incorrect persona assignment by scoping in or scoping out activities that might appear ambiguous from the persona description alone.

Questions are most valuable for personas with fuzzy or emerging boundaries. Personas with sharply distinct scopes (e.g., `personaModelServing`, whose separation from `personaModelProvider` is well-defined) may omit questions without loss of clarity.

**All non-deprecated personas should eventually have identification questions.** This is being phased in — currently three of eight non-deprecated personas have them (`personaModelProvider`, `personaAgenticProvider`, `personaEndUser`). The remaining five are gaps to be addressed in future PRs. Personas whose scope is unambiguously distinct from all adjacent personas may omit questions, but this should be a documented decision, not a default.

---

## Question Structure

### Count

Write 5–7 questions per persona. Fewer than 5 may leave gaps; more than 7 creates redundancy and reader fatigue.

### Format

All questions must be answerable with yes or no. Use second-person framing:

- `Do you...`
- `Are you...`
- `Does your...`

Do not use third-person framing ("Does the organization...") or rhetorical constructions ("Would you say that...").

### Avoid embedded conditionals

Each question must be a direct yes/no question. Do not nest conditions — if the first question opens with "Are you...", the subsequent questions may vary in opener, but none should require the reader to evaluate a conditional before answering.

---

## Content Principles

### Ask about activities, not titles

Questions should describe what the reader does, not what their role is called. Role names vary across organizations and industries; activities are stable.

**Avoid:**
> Are you a model engineer or ML researcher?

**Prefer:**
> Are you training or fine-tuning AI/ML models for use by others?

### Draw boundaries with scoping clauses

Where two personas could plausibly both claim the same activity, add a scoping clause that assigns the activity to exactly one persona.

**Example from `personaModelProvider` Q3:**
> Do you evaluate, benchmark, or perform quality assurance on AI/ML models **as part of training, adaptation, or distribution decisions**?

The clause "as part of training, adaptation, or distribution decisions" excludes runtime evaluation, which belongs to `personaModelServing`. Without this clause, both personas could answer yes to a question about model evaluation.

Write scoping clauses when:
- The activity described is performed by actors in more than one persona
- The persona boundary is defined by *context* or *intent* rather than the activity itself

### Use parenthetical examples for technical terms

When a technical term may be unfamiliar or has multiple interpretations, add a parenthetical example immediately after the term.

**Example from `personaModelProvider` Q2:**
> Do you modify, extend, or wrap existing models **(e.g., distillation, quantization, adaptation, or adding guardrails)** for use by others?

Keep examples to 2–4 items. Longer lists obscure the point; shorter lists may seem exclusive. Use "e.g." (not "i.e.") to signal that the list is illustrative, not exhaustive.

### Use "including" to widen scope intentionally

When a concept might be read narrowly and you intend broad coverage, use "including" followed by the subset you want to make explicit.

**Example from `personaModelProvider` Q1:**
> Are you training or fine-tuning AI/ML models for use by others, **including classical ML, statistical, optimization, and rule-based models**?

Without the "including" clause, a reader who works only with classical ML models (not neural networks) might incorrectly conclude this persona does not apply to them.

Use this pattern when the broader term is correct and complete, but readers are likely to interpret it narrowly based on common usage.

---

## Question Ordering

Order questions to guide the reader efficiently:

1. **Lead with the most distinguishing activity** — the one that most readers in this persona will recognize immediately as their own.
2. **Follow with scope-expanding questions** — activities that are less obvious but still core.
3. **End with boundary-clarifying questions** — questions that use scoping clauses or draw distinctions from adjacent personas.

This ordering helps a reader who identifies with question 1 quickly confirm they belong here, while also helping a reader who is uncertain use the later questions to distinguish between personas.

---

## Anti-patterns

**Overlapping questions without boundary clauses**

If two questions describe the same activity at different levels of abstraction, merge them or add a scoping clause to one.

**Overlapping questions:**
> Do you train AI models?
> Do you build or create machine learning models?

**Questions that only address job title or department**

> Are you on an ML platform team?
> Is your role classified as an AI engineer?

**Binary questions with embedded assumptions**

> Do you train models using GPU clusters in the cloud?

The "GPU clusters in the cloud" assumption excludes valid actors who train on-premises or with other hardware. Drop constraints that are not part of the persona boundary.

**Leading questions that nudge toward yes**

> Don't you think your organization trains and distributes AI models?

Questions must be neutral. A reader who should answer no must be able to recognize that from the plain text.

**Exhaustive catalogues instead of illustrative examples**

> Do you modify existing models (e.g., distillation, quantization, adaptation, pruning, knowledge distillation, INT8 quantization, LoRA fine-tuning, or PEFT)?

Two to four examples are enough. Longer lists distract from the question and imply the list is definitional rather than illustrative.

---

## Reviewer Checklist

When reviewing a PR that adds or modifies `identificationQuestions`:

- [ ] Count is between 5 and 7
- [ ] Every question is answerable yes or no
- [ ] All questions use second-person framing (`Do you`, `Are you`, `Does your`)
- [ ] Technical terms have parenthetical examples where needed
- [ ] "including" is used where the base term might be read too narrowly
- [ ] Each question asks about an activity, not a job title or organizational label
- [ ] Any activity shared with an adjacent persona has a scoping clause distinguishing between them
- [ ] Questions are ordered: most distinguishing first, boundary-clarifying last
- [ ] No two questions are effectively asking the same thing
- [ ] Parenthetical example lists are 2–4 items using "e.g."

---

## Related Documentation

- [Personas Guide](../guide-personas.md) — Overview of all current personas, their responsibilities, and framework mappings
- [Persona Model Design](../design/persona-design.md) — Design rationale for the current persona taxonomy, including decisions about which personas receive identification questions and why (forthcoming)
