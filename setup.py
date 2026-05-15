"""
setup.py for RageBot MCP

This script configures the project for installation using setuptools,
leveraging pyproject.toml for metadata and requirements.txt for dependencies.
"""
import toml
from setuptools import setup, find_packages
import os

# --- Read Metadata from pyproject.toml ---
with open("pyproject.toml", "r", encoding="utf-8") as f:
    pyproject_data = toml.load(f)

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
