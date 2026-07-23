#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OPENCODE_DIR = Path.home() / ".config" / "opencode"
SKILLS_DIR = OPENCODE_DIR / "skills"
PLUGINS_DIR = OPENCODE_DIR / "plugins"
TOOLS_DIR = OPENCODE_DIR / "tools"
COMMANDS_DIR = OPENCODE_DIR / "commands"
CONFIG_FILE = OPENCODE_DIR / "opencode.json"
MARKETPLACES_FILE = OPENCODE_DIR / "marketplaces.json"

DEFAULT_OFFICIAL_MP = "https://github.com/anthropics/claude-plugins-official.git"

def get_git_env():
    env = os.environ.copy()
    ssh_key_path = env.get("SSH_KEY_PATH")
    if ssh_key_path and "GIT_SSH_COMMAND" not in env:
        env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key_path} -o IdentitiesOnly=yes"

    ca_bundle = env.get("GIT_SSL_CAINFO") or env.get("SSL_CERT_FILE") or env.get("REQUESTS_CA_BUNDLE")
    if ca_bundle:
        env["GIT_SSL_CAINFO"] = ca_bundle
        env["SSL_CERT_FILE"] = ca_bundle

    return env

def load_marketplaces():
    if not MARKETPLACES_FILE.exists():
        return {"official": DEFAULT_OFFICIAL_MP, "claude-plugins-official": DEFAULT_OFFICIAL_MP}
    try:
        return json.loads(MARKETPLACES_FILE.read_text())
    except Exception:
        return {"official": DEFAULT_OFFICIAL_MP, "claude-plugins-official": DEFAULT_OFFICIAL_MP}

def save_marketplaces(data):
    OPENCODE_DIR.mkdir(parents=True, exist_ok=True)
    MARKETPLACES_FILE.write_text(json.dumps(data, indent=2))

def add_marketplace(name_or_url: str, url: str = None):
    marketplaces = load_marketplaces()
    if url is None:
        git_url = name_or_url
        clean = git_url.rstrip("/").removesuffix(".git")
        name = clean.split("/")[-1].split(":")[-1]
    else:
        name = name_or_url
        git_url = url

    marketplaces[name] = git_url
    save_marketplaces(marketplaces)
    print(f"✅ Registered marketplace '{name}': {git_url}")

def fetch_manifest_from_repo(repo_url: str) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        env = get_git_env()
        print(f"📥 Fetching marketplace catalog from Git: {repo_url}...")
        
        cmd = ["git", "clone", "--depth", "1"]
        if os.environ.get("GIT_SSL_NO_VERIFY", "").lower() in ["true", "1", "yes"]:
            cmd.extend(["-c", "http.sslVerify=false"])
            
        cmd.extend([repo_url, temp_dir])

        res = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"❌ Git clone failed: {res.stderr.decode().strip()}")
            sys.exit(1)

        manifest_path = Path(temp_dir) / ".claude-plugin" / "marketplace.json"
        if not manifest_path.exists():
            manifest_path = Path(temp_dir) / "marketplace.json"

        if not manifest_path.exists():
            print(f"❌ Could not find marketplace.json in repository '{repo_url}'.")
            sys.exit(1)

        return json.loads(manifest_path.read_text(encoding="utf-8"))

def merge_mcp_config(mcp_data: dict):
    config = {}
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    if "mcp" not in config:
        config["mcp"] = {}
    for server_name, server_cfg in mcp_data.items():
        config["mcp"][server_name] = server_cfg
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

def copy_and_prepare_directory(src_dir: Path, target_dir: Path, plugin_name: str):
    """Copies entire skill/plugin directory and ensures proper paths & executable bits."""
    target_dir.mkdir(parents=True, exist_ok=True)

    for root, _, files in os.walk(src_dir):
        rel_path = Path(root).relative_to(src_dir)
        dest_folder = target_dir / rel_path
        dest_folder.mkdir(parents=True, exist_ok=True)

        for file_name in files:
            src_file = Path(root) / file_name
            dest_file = dest_folder / file_name

            if ".git" in src_file.parts:
                continue

            if file_name.endswith(".md"):
                content = src_file.read_text(encoding="utf-8")
                content = re.sub(r"\$\{CLAUDE_PLUGIN_ROOT\}", str(target_dir), content)
                content = re.sub(r"\$\{CLAUDE_PROJECT_DIR\}", ".", content)

                if file_name.upper() in ["SKILL.MD", f"{plugin_name.upper()}.MD"] and not content.startswith("---"):
                    frontmatter = f"---\nname: {plugin_name}\ndescription: Ported from Claude plugin {plugin_name}\n---\n\n"
                    content = frontmatter + content

                dest_file.write_text(content, encoding="utf-8")
            else:
                shutil.copy2(src_file, dest_file)

            if src_file.suffix in [".sh", ".py", ".bash", ".js", ".ts"] or os.access(src_file, os.X_OK):
                os.chmod(dest_file, dest_file.stat().st_mode | 0o755)

def install_plugin(target_arg: str, force_update: bool = False):
    """Installs or updates a plugin. Avoids re-downloading if already installed unless force_update=True."""
    marketplaces = load_marketplaces()
    plugin_entry = None

    if "@" in target_arg:
        plugin_name, mp_target = target_arg.split("@", 1)
    else:
        plugin_name, mp_target = target_arg, None

    skill_target_dir = SKILLS_DIR / plugin_name

    if skill_target_dir.exists() and not force_update:
        print(f"ℹ️  Plugin '{plugin_name}' is already installed. Use 'opencode plugin update {plugin_name}' to force re-download.")
        return

    search_marketplaces = marketplaces
    if mp_target:
        if mp_target in marketplaces:
            search_marketplaces = {mp_target: marketplaces[mp_target]}
        else:
            search_marketplaces = {k: v for k, v in marketplaces.items() if mp_target in k or mp_target in v}
            if not search_marketplaces:
                print(f"❌ Targeted marketplace '{mp_target}' is not registered.")
                sys.exit(1)

    print(f"🔍 Searching for '{plugin_name}' in registered marketplace(s)...")

    for mp_name, mp_url in search_marketplaces.items():
        try:
            data = fetch_manifest_from_repo(mp_url)
            for p in data.get("plugins", []):
                if p.get("name") == plugin_name or p.get("displayName") == plugin_name:
                    plugin_entry = p
                    print(f"   Found in marketplace: {mp_name}")
                    break
        except Exception:
            continue
        if plugin_entry:
            break

    if not plugin_entry:
        print(f"❌ Plugin '{plugin_name}' not found.")
        sys.exit(1)

    source = plugin_entry.get("source", {}) if isinstance(plugin_entry, dict) else {}

    is_inline_plugin = False
    inline_path = None
    repo_url_for_clone = None
    path_in_repo = ""

    if isinstance(source, str):
        is_inline_plugin = True
        inline_path = source.lstrip("./")
        
        for mp_name, mp_url in search_marketplaces.items():
            repo_url_for_clone = mp_url
            break
    elif isinstance(source, dict):
        if source.get("source") == "git-subdir":
            repo_url_for_clone = source.get("url") or source.get("repo")
            path_in_repo = source.get("path", "")
        else:
            repo_url_for_clone = source.get("url") or source.get("repo")

    if skill_target_dir.exists() and force_update:
        print(f"🔄 Updating '{plugin_name}'... Removing existing version.")
        shutil.rmtree(skill_target_dir)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"📥 Cloning plugin repository: {repo_url_for_clone}...")
        
        env = get_git_env()
        cmd = ["git", "clone", "--depth", "1"]
        if os.environ.get("GIT_SSL_NO_VERIFY", "").lower() in ["true", "1", "yes"]:
            cmd.extend(["-c", "http.sslVerify=false"])
            
        cmd.extend([repo_url_for_clone, str(temp_path)])

        subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL)

        if is_inline_plugin and inline_path:
            src_dir = temp_path / inline_path
            print(f"📍 Using inline plugin path: {inline_path}")
        else:
            src_dir = temp_path / path_in_repo if path_in_repo else temp_path

        print(f"📂 Copying full skill bundle to: {skill_target_dir}")
        copy_and_prepare_directory(src_dir, skill_target_dir, plugin_name)

        for tool_file in src_dir.glob("tools/**/*"):
            if tool_file.is_file():
                rel = tool_file.relative_to(src_dir / "tools")
                dest = TOOLS_DIR / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tool_file, dest)
                if tool_file.suffix in [".sh", ".py", ".js", ".ts"]:
                    os.chmod(dest, dest.stat().st_mode | 0o755)

        for json_file in src_dir.glob("**/*.json"):
            try:
                jdata = json.loads(json_file.read_text())
                if "mcpServers" in jdata:
                    merge_mcp_config(jdata["mcpServers"])
                elif "mcp" in jdata:
                    merge_mcp_config(jdata["mcp"])
            except Exception:
                pass

    action_label = "updated" if force_update else "installed"
    print(f"🎉 Successfully {action_label} '{plugin_name}' into OpenCode!")

def update_plugins(target_arg: str = None):
    """Updates a specific plugin or all installed plugins."""
    if target_arg:
        install_plugin(target_arg, force_update=True)
    else:
        if not SKILLS_DIR.exists() or not any(SKILLS_DIR.iterdir()):
            print("ℹ️  No installed plugins found to update.")
            return

        installed = [item.name for item in SKILLS_DIR.iterdir() if item.is_dir()]
        print(f"🔄 Updating all {len(installed)} installed plugins...")
        for plugin_name in installed:
            install_plugin(plugin_name, force_update=True)

def list_marketplace_plugins(marketplace_name: str = None, search_term: str = None):
    """List available plugins from marketplace(s)."""
    marketplaces = load_marketplaces()
    
    target_mp = None
    if marketplace_name:
        if marketplace_name in marketplaces:
            target_mp = {marketplace_name: marketplaces[marketplace_name]}
        else:
            print(f"❌ Marketplace '{marketplace_name}' is not registered.")
            sys.exit(1)
    
    search_marketplaces = target_mp if target_mp else marketplaces
    
    all_plugins = []
    for mp_name, mp_url in search_marketplaces.items():
        try:
            manifest = fetch_manifest_from_repo(mp_url)
            plugins = manifest.get("plugins", [])
            for p in plugins:
                display_name = p.get("name") or p.get("displayName", "Unknown")
                if search_term and search_term.lower() not in display_name.lower():
                    continue
                all_plugins.append((display_name, mp_name))
        except Exception as e:
            print(f"⚠️  Could not fetch from marketplace '{mp_name}': {e}")
    
    if not all_plugins:
        query = f" matching '{search_term}'" if search_term else ""
        print(f"🔍 No plugins found{query} in marketplace(s).")
        return
    
    for name, mp in sorted(all_plugins):
        print(f"  • {name}")

def _list_marketplace_internal(marketplace_name: str = None):
    """List registered marketplaces (internal function for reuse)."""
    
    marketplaces = load_marketplaces()
    
    if not marketplaces:
        return []
    
    target_mps = [(name, url) for name, url in marketplaces.items()]
    
    if marketplace_name and marketplace_name != "official":
        filtered = {k: v for k, v in marketplaces.items() 
                    if marketplace_name in k or marketplace_name in v}
        if filtered:
            target_mps = list(filtered.items())
    
    result = []
    for alias, url in sorted(target_mps):
        status = ""
        try:
            subprocess.run(["git", "ls-remote", "--exit-code", url], 
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            status = " (unreachable)"
        result.append((alias, url, status))
    return result

def list_marketplace(marketplace_name: str = None):
    """List registered marketplaces."""
    mps = _list_marketplace_internal(marketplace_name)
    
    if not mps:
        print("❌ No marketplaces registered.")
        sys.exit(1)
    
    print(f"🛒 Registered Marketplaces:")
    for alias, url, status in mps:
        print(f"  • {alias} => {url}{status}")

def remove_marketplace(name_or_url: str):
    """Remove a registered marketplace."""
    marketplaces = load_marketplaces()
    
    if name_or_url not in marketplaces and name_or_url != "official":
        print(f"❌ Marketplace '{name_or_url}' is not registered.")
        sys.exit(1)
    
    del marketplaces[name_or_url]
    save_marketplaces(marketplaces)
    print(f"✅ Removed marketplace '{name_or_url}'")

def enable_plugin(plugin_name: str):
    """Enable a disabled plugin."""
    skill_path = SKILLS_DIR / plugin_name
    
    if not skill_path.exists():
        print(f"❌ Plugin '{plugin_name}' is not installed.")
        sys.exit(1)
    
    disabled_marker = SKILLS_DIR / f"{plugin_name}.disabled"
    if disabled_marker.exists():
        disabled_marker.unlink()
        print(f"✅ Enabled plugin '{plugin_name}'")
    else:
        print(f"ℹ️  Plugin '{plugin_name}' is already enabled.")

def disable_plugin(plugin_name: str):
    """Disable a plugin (but keep it installed)."""
    skill_path = SKILLS_DIR / plugin_name
    
    if not skill_path.exists():
        print(f"❌ Plugin '{plugin_name}' is not installed.")
        sys.exit(1)
    
    disabled_marker = SKILLS_DIR / f"{plugin_name}.disabled"
    if disabled_marker.exists():
        print(f"ℹ️  Plugin '{plugin_name}' is already disabled.")
    else:
        disabled_marker.touch()
        print(f"✅ Disabled plugin '{plugin_name}'")

def remove_plugin(plugin_name: str):
    """Remove an installed plugin."""
    skill_path = SKILLS_DIR / plugin_name
    
    if not skill_path.exists():
        print(f"❌ Plugin '{plugin_name}' is not installed.")
        sys.exit(1)
    
    shutil.rmtree(skill_path)
    print(f"✅ Removed plugin '{plugin_name}'")

def list_installed():
    """List all installed plugins and marketplaces."""
    print("📋 Installed Plugins & Marketplaces:\n")
    
    print("🔧 Installed Plugins:")
    if SKILLS_DIR.exists() and any(SKILLS_DIR.iterdir()):
        skills = [item for item in SKILLS_DIR.iterdir() if item.is_dir()]
        for skill in sorted(skills):
            disabled_marker = SKILLS_DIR / f"{skill.name}.disabled"
            status = " (disabled)" if disabled_marker.exists() else ""
            print(f"  • {skill.name}{status}")
    else:
        print("  (none installed)")
    
    print("\n🛒 Registered Marketplaces:")
    mps = _list_marketplace_internal()
    for alias, url, status in mps:
        print(f"  • {alias} => {url}{status}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="opencode plugin")
    subparsers = parser.add_subparsers(dest="command")

    install_parser = subparsers.add_parser("install", aliases=["add"], help="Install a plugin from marketplace")
    install_parser.add_argument("plugin_name", help="Plugin name or 'name@marketplace'")
    
    update_parser = subparsers.add_parser("update", aliases=["upgrade"], help="Update installed plugins")
    update_parser.add_argument("target", nargs="?", help="Specific plugin to update, or omit for all")

    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List installed artifacts and marketplaces")

    remove_parser = subparsers.add_parser("remove", help="Remove an installed plugin")
    remove_parser.add_argument("plugin_name", help="Plugin name to remove")
    
    enable_parser = subparsers.add_parser("enable", help="Enable a disabled plugin")
    enable_parser.add_argument("plugin_name", help="Plugin name to enable")
    
    disable_parser = subparsers.add_parser("disable", help="Disable an installed plugin")
    disable_parser.add_argument("plugin_name", help="Plugin name to disable")

    marketplace_parser = subparsers.add_parser("marketplace", help="Manage marketplaces")
    mp_subparsers = marketplace_parser.add_subparsers(dest="mp_command")

    mp_add = mp_subparsers.add_parser("add", help="Add a marketplace")
    mp_add.add_argument("alias_or_url", help="Marketplace alias or Git URL")
    mp_add.add_argument("url", nargs="?", help="Git URL (if first arg is an alias)")
    
    mp_list = mp_subparsers.add_parser("list", help="List registered marketplaces")
    mp_list.add_argument("name", nargs="?", help="Filter by marketplace name/alias")

    mp_remove = mp_subparsers.add_parser("remove", help="Remove a marketplace")
    mp_remove.add_argument("name_or_url", help="Marketplace alias or URL to remove")

    mp_update = mp_subparsers.add_parser("update", aliases=["search"], help="Search for plugins in marketplaces")
    mp_update.add_argument("search_term", nargs="?", help="Search term to filter plugins")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "install":
        install_plugin(args.plugin_name, force_update=False)
    
    elif args.command in ["update", "upgrade"]:
        update_plugins(args.target)
    
    elif args.command in ["list", "ls"]:
        list_installed()
    
    elif args.command == "remove":
        remove_plugin(args.plugin_name)
    
    elif args.command == "enable":
        enable_plugin(args.plugin_name)
    
    elif args.command == "disable":
        disable_plugin(args.plugin_name)
    
    elif args.command == "marketplace":
        if not args.mp_command:
            marketplace_parser.print_help()
            sys.exit(1)

        if args.mp_command == "add":
            add_marketplace(args.alias_or_url, args.url)
        
        elif args.mp_command == "list":
            list_marketplace(args.name)
        
        elif args.mp_command in ["remove"]:
            remove_marketplace(args.name_or_url)
        
        elif args.mp_command in ["update", "search"]:
            list_marketplace_plugins(search_term=args.search_term)

