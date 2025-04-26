from setuptools import setup, find_packages

setup(
    name="market_research_core_py",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "markdown>=3.3.0",
    ],
    extras_require={
        "rust": ["market_research_core"],
    },
    description="High-performance market research utilities with Rust acceleration",
    author="Your Name",
    python_requires=">=3.8",
) 