from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-gpui-ui",
    version="1.0.0",
    description="Agent-native CLI to drive and test the gpui-ui component gallery (GPUI).",
    long_description=open("cli_anything/gpui_ui/README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.gpui_ui": ["skills/*.md", "README.md", "tests/TEST.md"],
    },
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    extras_require={
        "test": ["pytest>=7"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-gpui-ui=cli_anything.gpui_ui.gpui_ui_cli:main",
        ],
    },
    python_requires=">=3.10",
)
