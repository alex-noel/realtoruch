"""Test the commit helper's Git argument handling."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import commit


@pytest.mark.parametrize("selector", [[], ["--task", "Q01"], ["--task=Q40"]])
@pytest.mark.parametrize("arguments", [["-m", "Fixture"], ["--amend", "--no-edit"]])
def test_commit_arguments_are_forwarded_to_git(monkeypatch, selector, arguments):
    def run(argv, *, cwd, check):
        assert argv == ["git", "commit", *arguments]
        assert cwd == Path(__file__).resolve().parents[2]
        assert check is False
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(commit.sys, "argv", ["commit.py", *selector, *arguments])
    monkeypatch.setattr(commit.subprocess, "run", run)
    assert commit.main() == 7


@pytest.mark.parametrize("arguments", [["--task"], ["--task=Q00"], ["--task=Q41"], ["--task=Q01", "--task=Q02"]])
def test_invalid_task_selector_fails_before_git(monkeypatch, arguments):
    monkeypatch.setattr(commit.sys, "argv", ["commit.py", *arguments])
    monkeypatch.setattr(commit.subprocess, "run", lambda *a, **k: pytest.fail("Git must not run"))
    with pytest.raises(SystemExit):
        commit.main()
