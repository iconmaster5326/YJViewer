import os
import pathlib

import setuptools
import setuptools.command.build_py
import setuptools.command.install
import setuptools.command.sdist

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

PKG_NAME = "yjviewer"

exec((here / "src" / PKG_NAME / "version.py").read_text(encoding="utf-8"))

setuptools.setup(
    name=PKG_NAME,
    version=__version__,
    description="A web application that lets you view YGOJSON data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iconmaster5326/YJViewer",
    author="iconmaster5326",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="yugioh,ygo,ygojson",
    packages=setuptools.find_packages("src"),
    python_requires=">=3.8, <4",
    install_requires=["Flask", "lark", "ygojson"],
    extras_require={
        "dev": ["pre-commit", "watchdog"],
        "test": [],
    },
    package_dir={
        "": "src",
    },
    # entry_points={
    #     "console_scripts": [
    #         f"{PKG_NAME}={PKG_NAME}.__main__:main",
    #     ],
    # },
)
