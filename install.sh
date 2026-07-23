#!/usr/bin/env bash
set -e

# Resolve repository directory
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_SCRIPT="$REPO_DIR/opencode-plugin-mgr.py"

echo "🚀 Installing opencode-plugin-mgr..."

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Error: Could not find 'opencode-plugin-mgr.py' in '$REPO_DIR'."
    exit 1
fi

# 1. Ensure target directories exist
BIN_DIR="$HOME/.local/bin"
OPENCODE_DIR="$HOME/.config/opencode"
mkdir -p "$BIN_DIR"
mkdir -p "$OPENCODE_DIR/skills"
mkdir -p "$OPENCODE_DIR/plugins"
mkdir -p "$OPENCODE_DIR/tools"
mkdir -p "$OPENCODE_DIR/commands"

TARGET_BINARY="$BIN_DIR/opencode-plugin-mgr"

# 2. Copy the Python script into ~/.local/bin/ and make it executable
cp "$PYTHON_SCRIPT" "$TARGET_BINARY"
chmod +x "$TARGET_BINARY"
echo "✅ Installed script to $TARGET_BINARY"

# 3. Configure Shell Alias Function
SHELL_CONFIG=""
if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
fi

ALIAS_BLOCK='
# OpenCode Claude Plugin Manager Interceptor
opencode() {
    if [ "$1" = "plugin" ]; then
        shift
        ~/.local/bin/opencode-plugin-mgr "$@"
    else
        command opencode "$@"
    fi
}
'

if [ -n "$SHELL_CONFIG" ]; then
    if ! grep -q "opencode-plugin-mgr" "$SHELL_CONFIG"; then
        echo "$ALIAS_BLOCK" >> "$SHELL_CONFIG"
        echo "✅ Added 'opencode plugin' wrapper alias to $SHELL_CONFIG"
        echo ""
        echo "🎉 Installation complete! Please reload your shell:"
        echo "   source $SHELL_CONFIG"
    else
        echo "ℹ️ Wrapper alias already present in $SHELL_CONFIG"
        echo "🚀 Installation complete!"
    fi
else
    echo "🚨 Warning: No .zshrc or .bashrc found."
    echo "Please manually add the following shell function:"
    echo "$ALIAS_BLOCK"
fi

