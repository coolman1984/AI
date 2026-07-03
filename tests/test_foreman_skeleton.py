"""Test FOREMAN skeleton: folders exist, gitignore is set up."""
import os

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOREMAN_FOLDERS = [
    "skills",
    "tools",
    "runs",
    "reports",
    "vault",
    "lessons",
    "schemas",
    "templates",
    "dashboards",
    "datasets/inbox",
    "datasets/registered",
    "logs",
    "approvals/pending",
    "approvals/decided",
    "registry",
    "evidence",
    "exports",
    "config",
]


@pytest.mark.parametrize("folder", FOREMAN_FOLDERS)
def test_folders_exist(folder):
    """Each FOREMAN folder must exist under the project root."""
    path = os.path.join(BASE, folder)
    assert os.path.isdir(path), f"Missing FOREMAN folder: {path}"


def test_required_tracked_folders_have_readme():
    """Tracked FOREMAN folders must have a README.md."""
    tracked = ["skills", "templates", "schemas", "registry", "vault"]
    for folder in tracked:
        readme = os.path.join(BASE, folder, "README.md")
        assert os.path.isfile(readme), f"Missing README in {folder}"
        content = open(readme).read().strip()
        assert len(content) > 10, f"README in {folder} is too short"


def test_gitignore_ignores_data_folders():
    """Data folders should be listed in .gitignore."""
    gitignore_path = os.path.join(BASE, ".gitignore")
    assert os.path.isfile(gitignore_path)
    content = open(gitignore_path).read()
    required = [
        "datasets/registered/",
        "runs/",
        "reports/",
        "logs/",
        "exports/",
        "evidence/",
        "approvals/",
        "registry/*.db",
    ]
    for entry in required:
        assert entry in content, f".gitignore missing entry: {entry}"


def test_existing_engines_untouched():
    """Existing engine directories must still exist."""
    existing = ["engines", "serving", "gov", "shared"]
    for d in existing:
        path = os.path.join(BASE, d)
        assert os.path.isdir(path), f"Existing dir was removed: {path}"
