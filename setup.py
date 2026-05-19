"""
setup.py for RageBot MCP

This script configures the project for installation using setuptools,
leveraging pyproject.toml for metadata and requirements.txt for dependencies.
"""
from setuptools import setup, find_packages
import os

# --- Read Metadata from pyproject.toml ---
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python 3.10
    except ImportError:
        try:
            import toml as tomllib  # Fallback for older versions
        except ImportError:
            # Final fallback: Use basic parsing
            import sys
            print("Warning: Could not import toml library. Using basic parsing.", file=sys.stderr)
            tomllib = None

# Parse pyproject.toml
if tomllib and hasattr(tomllib, 'load'):
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
else:
    # Basic fallback parsing
    with open("pyproject.toml", "r", encoding="utf-8") as f:
        pyproject_data = {}
        # This is a simplified parser - just extract what we need
        content = f.read()
        # Extract version line
        import re
        version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if version_match:
            pyproject_data = {
                "project": {
                    "name": "ragebot-mcp",
                    "version": version_match.group(1),
                    "description": "Intelligent CLI-based Project Context Engine with MCP server support",
                    "readme": "README.md",
                    "requires-python": ">=3.10",
                    "license": {"text": "MIT"},
                    "authors": [{"name": "RageBot Team"}],
                    "keywords": ["cli", "ai", "mcp", "gemini", "grok"],
                    "scripts": {
                        "ragebot": "ragebot.cli:main_interactive",
                        "rage": "ragebot.cli:main",
                        "ragebot-mcp-server": "ragebot.mcp.server:main",
                    }
                },
                "tool": {
                    "setuptools": {
                        "packages": {"find": {"where": ["."], "include": ["ragebot*"]}}
                    }
                }
            }

project_metadata = pyproject_data.get("project", {})

project_name = project_metadata.get("name", "ragebot-mcp")
project_version = project_metadata.get("version", "0.1.0")
project_description = project_metadata.get("description", "")
project_authors = project_metadata.get("authors", [{"name": "RageBot Team"}])
project_license = project_metadata.get("license", {"text": "MIT"})
project_keywords = project_metadata.get("keywords", [])
project_readme = project_metadata.get("readme", "README.md")
project_requires_python = project_metadata.get("requires-python", ">=3.10")

# Read long description from README.md
long_description_content = ""
if os.path.exists(project_readme):
    with open(project_readme, "r", encoding="utf-8") as f:
        long_description_content = f.read()

# --- Read Dependencies from requirements.txt ---
install_requires_list = []
if os.path.exists("requirements.txt"):
    with open("requirements.txt", "r", encoding="utf-8") as f:
        # Filter out comments and empty lines
        install_requires_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# --- Define Entry Points from pyproject.toml ---
console_scripts_list = []
if "project" in pyproject_data and "scripts" in pyproject_data["project"]:
    for name, module_func in pyproject_data["project"].get("scripts", {}).items():
        console_scripts_list.append(f"{name} = {module_func}")

# --- Define Package Discovery from pyproject.toml ---
package_dirs = ['.']
package_include = ['ragebot*']

if "tool" in pyproject_data and "setuptools" in pyproject_data["tool"] and "packages" in pyproject_data["tool"]["setuptools"]:
    setuptools_config = pyproject_data["tool"]["setuptools"]
    if "find" in setuptools_config:
        find_config = setuptools_config["find"]
        package_dirs = find_config.get("where", package_dirs)
        package_include = find_config.get("include", package_include)

# --- Setup function call ---
setup(
    name=project_name,
    version=project_version,
    description=project_description,
    long_description=long_description_content,
    long_description_content_type="text/markdown",
    author=project_authors[0].get("name", "RageBot Team") if project_authors else "RageBot Team",
    author_email=", ".join([author.get("email", "") for author in project_authors]) if project_authors else "",
    license=project_license.get("text", "MIT"),
    keywords=project_keywords,
    packages=find_packages(where=package_dirs[0], include=package_include), # Assumes first dir in 'where' is the base
    install_requires=install_requires_list,
    entry_points={
        "console_scripts": console_scripts_list
    },
    python_requires=project_requires_python,
    # If you have data files or other specific packaging needs, add them here
    # package_data={'': ['*.json', '*.yaml']},
    # include_package_data=True,
)
