# Expanding the CoSAI Risk Map

> This guide complements the repository-wide [`CONTRIBUTING.md`](../../CONTRIBUTING.md). Use that for branching, commit/PR workflow, code review expectations, and CLA. This document focuses on how to author and validate Risk Map content (schemas and YAML).
>
> _Note: all contributions discussed in this document would fall under the [Content Update Process](../../CONTRIBUTING.md#content-update-governance-process) covered in detail in the `CONTRIBUTING.md` document_

This guide outlines how you can contribute to the Coalition for Secure AI (CoSAI) Risk Map. By following these steps, you can help expand the framework while ensuring your contributions are consistent with the project's structure and pass all validation checks.

---

## Documentation Index

### Getting Started

**[Setup & Prerequisites](setup.md)**

- Installing dependencies and pre-commit hooks
- Setting up Python, Node.js, and validation tools
- Platform-specific configuration for SVG generation

### Development Tools

**[Validation Tools](validation.md)**

- Manual edge validation and graph generation
- Markdown table documentation
- Control-to-risk reference validation
- Prettier formatting and Ruff linting
- Command reference for all validation tools

**[Graph Customization](graph-customization.md)**

- Customizing Mermaid graph appearance
- Foundation design tokens and color schemes
- Graph layout and spacing configuration
- Testing and visualizing customizations
- Common customization examples

**[CI/CD Validation](ci-cd.md)**

- GitHub Actions automated validation
- Graph validation in pull requests
- SVG generation from Mermaid diagrams
- Handling CI validation failures

### Contributing Content

**[General Contribution Workflow](workflow.md)**

- Overall process for contributing content
- Using validation tools during development
- Creating pull requests

**[Issue Templates Guide](contributing/issue-templates-guide.md)**

- Using GitHub issue templates to propose new content or updates
- Complete guide for all 9 available templates
- Examples, required fields, and automatic bidirectionality
- Framework applicability and schema evolution guidance

**[Template Sync Procedures](contributing/template-sync-procedures.md)** _(For Maintainers)_

- How templates stay synchronized with schemas
- Manual synchronization procedures
- Two-week sync lag explanation
- Automation roadmap and troubleshooting

**Content Addition Guides:**

- **[Adding a Component](guide-components.md)** - Add new components to the AI system architecture
- **[Adding a Control](guide-controls.md)** - Add new security controls and map them to components/risks
- **[Adding a Risk](guide-risks.md)** - Add new security risks with proper categorization
- **[Adding a Persona](guide-personas.md)** - Add new roles in the AI ecosystem
- **[Adding and Using Frameworks](guide-frameworks.md)** - Map risks and controls to external security frameworks

### Reference

**[Troubleshooting](troubleshooting.md)**

- Edge validation errors
- Graph generation issues
- Common problems and solutions

**[Best Practices](best-practices.md)**

- Development workflow recommendations
- Validation strategies
- Documentation standards
- Graph preview techniques

**[Writing Documentation](writing-documentation.md)**

- How to write testable Python code examples
- Skip markers for documentation-only code
- Working directory and file path guidelines
- Testing examples locally

---

## Quick Links

- [Repository CONTRIBUTING.md](../../CONTRIBUTING.md) - Branch strategy, PR workflow, CLA
- [Scripts Documentation](../../scripts/README.md) - Git hooks and validation scripts
- Component Schema: `risk-map/schemas/components.schema.json`
- Controls Schema: `risk-map/schemas/controls.schema.json`
- Risks Schema: `risk-map/schemas/risks.schema.json`
- Personas Schema: `risk-map/schemas/personas.schema.json`
- Frameworks Schema: `risk-map/schemas/frameworks.schema.json`
