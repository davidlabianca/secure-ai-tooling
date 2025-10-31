# General Content Contribution Workflow

This page outlines the overall process for contributing content to the CoSAI Risk Map.

## Contribution Steps

1. **Create a GitHub issue** to track your work (see [Best Practices](best-practices.md))
2. Read the repository-wide [CONTRIBUTING.md](../../CONTRIBUTING.md) and follow the [Content Update Branching Process](../../CONTRIBUTING.md#for-content-updates-two-stage-process) for all content authoring
3. **Set up pre-commit hooks** (see [Setup & Prerequisites](setup.md))
4. Make content changes per the guides below (components, controls, risks, personas)
5. **Validate your changes** against all validation rules:
   - JSON Schema validation
   - Prettier YAML formatting
   - Ruff Python linting (if modifying Python files)
   - Component edge consistency
   - Control-to-risk reference consistency
6. Open a PR against the `develop` branch describing the Risk Map updates and validation performed
   - GitHub Actions will automatically run the same validations on your PR
   - Address any CI failures before requesting review

## Content Type Guides

Choose the guide that matches what you're adding:

- **[Adding a Component](guide-components.md)** - Add new components to the AI system architecture
- **[Adding a Control](guide-controls.md)** - Add new security controls and map them to components/risks
- **[Adding a Risk](guide-risks.md)** - Add new security risks with proper categorization
- **[Adding a Persona](guide-personas.md)** - Add new roles in the AI ecosystem

## Validation Tools

See [Validation Tools](validation.md) for detailed information on:
- Manual edge validation and graph generation
- Control-to-risk reference validation
- Markdown table generation
- Prettier formatting
- Ruff linting

## CI/CD

See [CI/CD Validation](ci-cd.md) for information on automated validation that runs on pull requests.

---

**Next Steps:** Choose a content type guide above to get started with your contribution.
