import os

import setuptools

with open("requirements.txt") as reqs:
    install_requires = reqs.read().splitlines()

with open("optional-requirements.txt") as reqs:
    extras_require = {}
    current = []
    for line in reqs.read().splitlines():
        if line.startswith("#/"):
            extras_require[line[2:]] = current = []
        elif not line or line.startswith("#"):
            continue
        else:
            current.append(line)

extras_require["all"] = list({dep for deps in extras_require.values() for dep in deps})

path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "menuflow", "__meta__.py")
__version__ = "UNKNOWN"
with open(path) as f:
    exec(f.read())

setuptools.setup(
    name="menuflow",
    version=__version__,
    url="https://github.com/bramenn/menuflow",
    project_urls={
        "Changelog": "https://github.com/bramenn/menuflow/blob/master/CHANGELOG.md",
    },
    author="Alejandro Herrera",
    author_email="bramendec@gmail.com",
    description="A manager of bots that have conversation flows",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires="~=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Topic :: Communications :: Chat",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    data_files=[
        (".", ["menuflow/example-config.yaml"]),
    ],
    package_data={
        "menuflow": [
            "example-config.yaml",
        ],
    },
)
