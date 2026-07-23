# OpenCode Plugin Manager

A standalone CLI tool to import, convert, and install **Claude Code marketplace plugins** into **OpenCode**.

This utility preserves full plugin structures—including Python/Bash scripts, JavaScript/TypeScript hooks, custom tools, and MCP servers—and converts them for use with OpenCode's native paths.

> ⚠️ **Note:** This is NOT an official Claude or Anthropic tool. It is a third-party utility created to bridge Claude marketplace plugins with OpenCode.

> ℹ️ **Testing Note:** While the conversion logic handles common plugin patterns, **not all plugins have been tested**. Different plugins may require manual adjustments. If you encounter issues with a specific plugin:
> - Check if path variables need updating after installation
> - Verify any hardcoded paths in scripts/tools work for your environment  
> - Review MCP configurations manually if server connections fail

## 📦 Installation

### Install Script (Recommended)
```bash
git clone https://github.com/lstav/opencode_plugin_manager.git ~/.opencode-plugin-manager
cd ~/.opencode-plugin-manager
chmod +x install.sh && ./install.sh
source ~/.bashrc  # or source ~/.zshrc
```

This installs the manager and creates a shell wrapper so `opencode plugin <command>` works seamlessly alongside the official OpenCode CLI.

### Manual Installation (Alternative)
```bash
# Run directly without installation
python3 path/to/opencode-plugin-mgr.py <command>

# Or add to PATH for convenience  
export PATH="$PATH:/path/to/opencode_plugin_manager"
opencode-plugin-mgr.py plugin install <plugin-name>
```

---

## 🚀 Usage Guide

Once installed via `install.sh`, use it like the official OpenCode CLI:

### 1. Register a Marketplace Repository
Add Git repositories containing marketplace manifests (marketplace.json):

```bash
# Add with custom alias for future use
opencode plugin marketplace add my-tools https://github.com/org/claude-plugins.git

# List all registered marketplaces  
opencode plugin marketplace list

# SSH URLs also supported
opencode plugin marketplace add private git@github.com:org/private-plugins.git
```

### 2. Install a Plugin
Install from any registered marketplace:

```bash
# Search all registered marketplaces and install
opencode plugin install frontend-design

# Target specific marketplace directly
opencode plugin install my-plugin@my-tools

# Force reinstall (redownloads even if already installed)
opencode plugin install --force my-plugin
```

**Special:** Some plugins have `source` as a string path (e.g., `"external_plugins/github"`) pointing to directories within the same marketplace repo. This is handled automatically.

### 3. Update Installed Plugins
Update individual or all installed plugins:

```bash
# Update specific plugin  
opencode plugin update frontend-design

# Update ALL installed plugins
opencode plugin update

# Aliases available: upgrade, ls for list
opencode plugin upgrade  # same as update
```

### 4. List Installed Artifacts
```bash
opencode plugin list      # or use alias 'ls'
opencode plugin marketplace search github   # find plugins by name
```

### 5. Remove a Plugin
```bash
opencode plugin remove my-custom-tool
```

### 6. Enable/Disable Plugins
Temporarily disable without uninstalling:

```bash
# Disable (creates .disabled marker file)
opencode plugin disable frontend-design

# Re-enable later  
opencode plugin enable frontend-design
```

### 7. Manage Marketplaces
```bash
# List marketplaces with reachability status
opencode plugin marketplace list

# Remove by name or URL
opencode plugin marketplace remove my-tools
opencode plugin marketplace remove https://github.com/url.git

# Search plugins in registered marketplaces  
opencode plugin marketplace search github
```

---

## 📂 File Handling Architecture

When running `opencode plugin install <name>`:

| Component | Destination | Behavior |
|-----------|-------------|----------|
| Plugin directory tree | `~/.config/opencode/skills/<name>/` | Recursive copy, `.git` excluded |
| Script files (`.py`, `.sh`, `.js`, `.ts`) | Same location | Preserves structure, adds executable bit (chmod +x) |
| Markdown files (`/*.md`, `*.MD`) | Processed & copied | Substitutes `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PROJECT_DIR}` variables |
| Tools directory (`/tools/**/*`) | `~/.config/opencode/tools/` | Copied with parent directories preserved |
| MCP configs (`*.json` w/ `mcpServers`/`mcp`) | Merged into `~/.config/opencode/opencode.json` | Merges with existing config |

### Path Variable Substitution
The following placeholders in markdown files are replaced:
- `${CLAUDE_PLUGIN_ROOT}` → `/home/user/.config/opencode/skills/<plugin-name>`  
- `${CLAUDE_PROJECT_DIR}` → `.` (current project directory)

---

## 🔧 Environment Variables

```bash
# Use SSH key for git operations
export SSH_KEY_PATH=~/.ssh/id_rsa

# Skip SSL verification (for self-signed certificates)
export GIT_SSL_NO_VERIFY=true  # or "1" or "yes"
```

---

## 📄 License

MIT Licensed - see [LICENSE](LICENSE) file for details.

