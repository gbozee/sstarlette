#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re

from setuptools import setup


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    with open(os.path.join(package, "__init__.py")) as f:
        return re.search("__version__ = ['\"]([^'\"]+)['\"]", f.read()).group(1)


def get_long_description():
    """
    Return the README.
    """
    with open("README.md", encoding="utf8") as f:
        return f.read()


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [
        dirpath
        for dirpath, dirnames, filenames in os.walk(package)
        if os.path.exists(os.path.join(dirpath, "__init__.py"))
    ]


setup(
    name="sstarlette",
    version=get_version("sstarlette"),
    python_requires=">=3.6",
    license="BSD",
    description="Enhancing Starlette Application",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Biola Oyeniyi",
    author_email="b33sama@gmail.com",
    packages=get_packages("sstarlette"),
    # package_data={"databases": ["py.typed"]},
    # data_files=[("", ["LICENSE.md"])],
    install_requires=["starlette>=0.13.0", "pyjwt==1.7.1", "pydantic[email]==1.2",],
    extras_require={
        "sentry": ["sentry-sdk"],
        "sql": [
            "databases==0.2.6",
            # "orm==0.0.8 @ https://github.com/gbozee/dalchemy/archive/0.0.8.zip",
        ],
    },
    dependency_links=["https://github.com/gbozee/dalchemy/archive/0.0.8.zip"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    zip_safe=False,
)
