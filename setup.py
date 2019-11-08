#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages
from pathlib import Path

HERE = Path(__file__).resolve()

with open("README.rst") as readme_file:
    readme = readme_file.read()

requirements = ["IMDbPY>=6.5"]

setup_requirements = []

test_requirements = []

setup(
    author="Matthew A. Clapp",
    author_email="itsayellow+dev@gmail.com",
    python_requires=">=3.5",
    classifiers=[
        "Development Status :: 3 Beta",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Creates pytivo metadata for video files.",
    entry_points={"console_scripts": ["pytivometa = pytivometa.pytivometa:cli_start"]},
    install_requires=requirements,
    long_description=readme + "\n",
    # include_package_data=True,
    package_data={"": ["*.pem"]},
    keywords="pytivo",
    name="pytivometa",
    url="https://github.com/itsayellow/pytivometa",
    packages=find_packages(include=["pytivometa", "pytivometa.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    # url='https://github.com/itsayellow/pytivometa',
    version="0.2.0",
    zip_safe=False,
)
