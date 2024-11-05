import logging
import os
import shutil
import subprocess

logger = logging.getLogger()
url_project = "https://github.com/iKonoTelecomunicaciones/menuflow"
cmd_env = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ["HOME"],
    "LANG": "C",
    "LC_ALL": "C",
}


# Run a command in the shell
def run(cmd):
    if os.path.exists(".git") and shutil.which("git"):
        try:
            return (
                subprocess.check_output(cmd, stderr=subprocess.DEVNULL, env=cmd_env)
                .strip()
                .decode("ascii")
            )
        except (subprocess.CalledProcessError, subprocess.SubprocessError, OSError) as err:
            if "--exact-match" in cmd:
                # If the command 'git describe --exact-match --tags' fails, it means there is no tag
                return None
            else:
                logger.error(f"------>Error: {err}")
            return None
    else:
        logger.error("Error: git not found")
        return None


# Get the latest tag from the git repository
def get_latest_tag():
    # Run the 'git describe --abbrev=0 --tags' command to get the latest development tag
    return run(["git", "describe", "--abbrev=0", "--tags"])


# Get the latest revision (commit) from the git repository
def get_latest_revision():
    # Run the 'git rev-parse HEAD' command to get the latest commit (revision)
    full_git_revision = run(["git", "rev-parse", "HEAD"])
    return full_git_revision[:8] if full_git_revision else None


# Check if the tag is linked to the latest commit
def is_latest_revision_tag(git_tag):
    # Run the 'git describe --exact-match --tags' command to get the latest revision tag
    stable_tag = run(["git", "describe", "--exact-match", "--tags"])
    return True if stable_tag and stable_tag == git_tag else False


# Update the __version__ variable in the init file
def update_init_file(version):
    with open("menuflow/__init__.py", "w") as init_file:
        init_file.write(f"# Generated from setup.py\n" f'__version__ = "{version}"\n')


# Get tag project from repository
def get_tag():
    # Getting latest tag
    git_tag = get_latest_tag()

    # Getting tag
    if git_tag and (is_latest_revision_tag(git_tag) or git_tag.endswith("+dev")):
        # If the tag is linked to latest commit or is a developer tag
        return git_tag
    elif git_tag and not git_tag.endswith("+dev"):
        # If the tag is not linked to latest commit, we add the revision to the developer version
        return f"{git_tag}+dev"
    else:
        # If there is no tag, we use the unknown tag as version
        return "v0.0.0.0+unknown"


# Get version project from repository
def get_version():
    # Getting tag
    git_tag = get_tag()

    # Getting version project
    if git_tag and git_tag.endswith("+dev"):
        return f"{git_tag[1:]}.{get_latest_revision()}"
    else:
        return git_tag[1:]


def get_version_link():
    # Getting tag
    git_tag = get_tag()

    # Getting version link project with tag or revision (commit) URL
    if git_tag and git_tag.endswith("+dev"):
        # with revision (commit) URL
        git_revision = get_latest_revision()
        return f"{git_tag}.[{git_revision}]({url_project}/-/commit/{git_revision})"
    else:
        # with tag URL
        return f"[{git_tag}]({url_project}/-/tags/{git_tag})"
