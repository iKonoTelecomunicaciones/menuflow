from logging import getLogger

import setuptools

from menuflow.git import (
    get_latest_revision,
    get_latest_tag,
    get_version,
    get_version_link,
    update_init_file,
)

log = getLogger("setup.py")

try:
    long_desc = open("README.md").read()
except IOError:
    long_desc = "Failed to read README.md"

with open("requirements.txt") as reqs:
    install_requires = reqs.read().splitlines()

with open("requirements-dev.txt") as reqs:
    extras_require = {}
    current = []
    for line in reqs.read().splitlines():
        if line.startswith("#/"):
            extras_require[line[2:]] = current = []
        elif not line or line.startswith("#"):
            continue
        else:
            current.append(line)

# Getting latest tag
git_latest_tag = get_latest_tag()
version = get_version()

log.critical(f"Version: {version}")
log.critical(f"git_latest_tag: {git_latest_tag}")
# Update the init file
if git_latest_tag:
    # git tag without 'v' prefix
    update_init_file(git_latest_tag[1:])

extras_require["all"] = list({dep for deps in extras_require.values() for dep in deps})

if version and git_latest_tag:
    with open("menuflow/version.py", "w") as version_file:
        version_file.write(
            "# Generated from setup.py\n"
            f'git_tag = "{get_latest_tag()}"\n'
            f'git_revision = "{get_latest_revision()}"\n'
            f'version = "{get_version()}"\n'
            f'version_link = "{get_version_link()}"\n'
        )

setuptools.setup(
    name="menuflow",
    version=version if version else git_latest_tag,
    url="https://github.com/iKonoTelecomunicaciones/menuflow",
    project_urls={
        "Changelog": "https://github.com/iKonoTelecomunicaciones/menuflow/blob/main/CHANGELOG.md",
    },
    author="iKono Telecomunicaciones S.A.S",
    author_email="desarrollo@ikono.com.co",
    description="App to design conversation flows that will make users interacting with it.",
    long_description=long_desc,
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
    ],
    package_data={
        "menuflow": [
            "example-config.yaml",
        ],
        "menuflow.web.api": ["components.yaml"],
    },
    data_files=[
        (".", ["menuflow/example-config.yaml"]),
    ],
)
