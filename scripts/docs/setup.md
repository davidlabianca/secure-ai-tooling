# Setup & Prerequisites

## Git Hooks Setup

**Prerequisites:**

- Python 3.14 or higher
- Node.js 22+ and npm
- Chrome/Chromium browser (for SVG generation from Mermaid diagrams)

Install dependencies and pre-commit hook (one-time setup):

```bash
# Install required Python packages
pip install -r requirements.txt

# Install Node.js dependencies (prettier, mermaid-cli, etc.)
npm install

# Install ruff (Python linter)
pip install ruff

# Install the pre-commit hook
./install-precommit-hook.sh
```

**Platform-specific Chrome/Chromium setup:**

- **Mac/Windows/Linux x64**: Chrome automatically handled by puppeteer (bundled with mermaid-cli dependencies)
- **Linux ARM64**: Requires manual Chromium setup since Google Chrome is not available for ARM64:

  ```bash
  # Option 1: Use Playwright Chromium (recommended)
  ./install-precommit-hook.sh --install-playwright

  # Option 2: Install system Chromium
  sudo apt install chromium-browser  # Ubuntu/Debian

  # Option 3: Specify custom Chromium path during installation
  ./install-precommit-hook.sh
  ```

## Requirements

Install all required Python packages:

```bash
pip install -r requirements.txt
```

**Required packages** (from `requirements.txt`):

- `PyYAML` - YAML file parsing and manipulation
- `check-jsonschema` - JSON schema validation for YAML files
- `pytest` - Testing framework for validation scripts
- `ruff` - Python linting and formatting

**Additional dependencies** (from `package.json`):

- `prettier` - Code formatting for YAML files
- `@mermaid-js/mermaid-cli` - Converts Mermaid diagrams to SVG files
- `playwright` - Provides Chromium browser for ARM64 Linux (optional)
- `puppeteer-core` - Browser automation library used by mermaid-cli

**Individual installation** (if needed):

```bash
pip install PyYAML check-jsonschema pytest ruff
npm install prettier @mermaid-js/mermaid-cli playwright puppeteer-core

# For ARM64 Linux specifically, install Playwright Chromium:
npx playwright install chromium --with-deps
```

## Hook Files

- `hooks/pre-commit` - The main git hook script that orchestrates all validations
- `hooks/validate_riskmap.py` - Python script for component edge validation
- `hooks/validate_control_risk_references.py` - Python script for control-risk cross-reference validation
- `install-precommit-hook.sh` - Installs all hooks to your local `.git/hooks/`

---

**Related:**
- [Hook Validations](hook-validations.md) - What the pre-commit hook does
- [Troubleshooting](troubleshooting.md) - Installation and setup issues
