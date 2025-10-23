# Setup & Prerequisites

Before contributing to the Risk Map, ensure you have the necessary validation tools set up.

## Setting Up Pre-commit Hooks

The repository includes automated schema validation, prettier YAML formatting, ruff Python linting, component edge consistency checks, control-to-risk reference validation, automatic graph generation, and Mermaid SVG generation via git pre-commit hooks.

**Prerequisites:**

- Python 3.10 or higher
- Node.js 18+ and npm
- Chrome/Chromium browser (for SVG generation from Mermaid diagrams)

1. **Install dependencies and pre-commit hook (one-time setup)**:

   ```bash
   # From the repository root
   # Install required Python packages
   pip install -r requirements.txt

   # Install Node.js dependencies (prettier, mermaid-cli, etc.)
   npm install

   # Install the pre-commit hook
   bash ./scripts/install-precommit-hook.sh
   ```

2. **Verify the hook is working**:
   ```bash
   # Make a test change to risk-map/yaml/components.yaml
   # Attempt to commit - the hook should run validation
   git add risk-map/yaml/components.yaml
   git commit -m "test commit"
   ```

## Platform Considerations for SVG Generation

The repository handles Mermaid diagrams with different approaches for local development versus GitHub Actions:

### Pre-commit Hooks (Local Development)

- **Automatic SVG Creation**: When Mermaid files (`.mmd`, `.mermaid`) are staged for commit, pre-commit hooks generate corresponding SVG files
- **Auto-staging**: Generated SVG files are automatically added to the commit
- **Location**: SVGs are created in `./risk-map/svg/` directory
- **Prerequisites**: Requires Chrome/Chromium browser and mermaid-cli

### Platform-Specific Setup

- **Mac/Windows/Linux x64**: Chrome automatically handled by puppeteer
- **Linux ARM64**: Requires manual Chromium setup:

  ```bash
  # Use the --install-playwright flag during setup
  ./scripts/install-precommit-hook.sh --install-playwright

  # Or install manually
  npx playwright install chromium --with-deps
  ```

---

**Next Steps:** See [Validation Tools](validation.md) for manual validation commands, or jump to the [General Contribution Workflow](workflow.md) to start contributing.
