from setuptools import setup, find_packages

setup(
    name="CircuitCollector",
    version="0.1",
    # auto find modules
    packages=find_packages(),
    install_requires=[
        "jinja2",
        "toml",
    ],
    python_requires=">=3.11",
    author="Shikai Wang",
    description="Analog circuit testbench generator and simulation framework.",
)
