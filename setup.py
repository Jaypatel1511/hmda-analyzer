from setuptools import setup, find_packages

setup(
    name="hmda-analyzer",
    version="0.2.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=1.4.0",
        "numpy>=1.21.0",
        "requests>=2.27.0",
    ],
)
