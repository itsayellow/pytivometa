#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages
from pathlib import Path

HERE = Path(__file__).resolve()

with open("README.rst") as readme_file:
    readme = readme_file.read()

requirements = []

setup_requirements = []

test_requirements = []

setup(
    author="Matthew A. Clapp",
    author_email="itsayellow+dev@gmail.com",
    python_requires=">=3.5",
    classifiers=[
        "Development Status :: 3 Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Creates metadata for pytivo corresponding to video files.",
    entry_points={
        "console_scripts": ["pytivometa = pytivometa.cli:pytivometa"]
    },
    install_requires=requirements,
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="pytivo",
    name="pytivometa",
    packages=find_packages(include=["pytivometa", "pytivometa.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    # url='https://github.com/itsayellow/pymclapp',
    version="0.1.0",
    zip_safe=False,
)
