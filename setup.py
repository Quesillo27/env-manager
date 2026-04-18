from setuptools import setup, find_packages

setup(
    name="env-manager",
    version="1.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.7",
        "cryptography>=41.0.7",
        "rich>=13.7.1",
    ],
    extras_require={
        "dev": ["pytest>=7.4", "pytest-mock>=3.11"],
    },
    entry_points={
        "console_scripts": [
            "env-manager=env_manager.cli:main",
        ],
    },
    python_requires=">=3.10",
)
