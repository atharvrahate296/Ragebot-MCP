from pathlib import Path
from setuptools import find_packages, setup

HERE = Path(__file__).resolve().parent

long_description = ""
readme_path = HERE / "README.md"
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

requirements_path = HERE / "requirements.txt"
install_requires = []
if requirements_path.exists():
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        install_requires.append(requirement)

setup(
    name="ragebot-mcp",
    version="1.0.0",
    description="Intelligent CLI-based Project Context Engine with MCP server support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="RageBot Team",
    author_email="",
    url="https://github.com/atharvrahate296/Ragebot-MCP",
    project_urls={
        "Source": "https://github.com/atharvrahate296/Ragebot-MCP",
        "Tracker": "https://github.com/atharvrahate296/Ragebot-MCP/issues",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Utilities",
    ],
    keywords="ai cli mcp gemini grok context code-search code-assistant",
    packages=find_packages(include=["ragebot*"]),
    python_requires=">=3.10",
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "ragebot = ragebot.cli:main_interactive",
            "rage = ragebot.cli:main",
            "ragebot-mcp-server = ragebot.mcp.server:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
