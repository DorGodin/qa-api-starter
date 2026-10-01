import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import mutate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def catalogue(tmp_path: Path, mutants: list[dict]) -> Path:
    path = tmp_path / "catalogue.yml"
    path.write_text(
        yaml.safe_dump({"product": "p", "mutants": mutants}, allow_unicode=True), encoding="utf-8"
    )
    return path


def mutant(
    name="breaks a rule", file="app/rule.py", catches=("api",), find="return True", replace="return False"
):
    return {
        "name": name,
        "file": file,
        "catches": list(catches),
        "changes": [{"find": find, "replace": replace}],
    }


def test_the_real_catalogue_loads_and_every_mutant_names_a_known_suite():
    mutants = mutate.load_catalogue(ROOT / "mutants" / "barber-booking.yml")

    assert len(mutants) >= 40
    assert all(set(m.catches) <= set(mutate.SUITES) for m in mutants)
    assert {"api", "ui", "load"} <= {
        suite for m in mutants for suite in m.catches
    }, "every suite has a mutant to catch"


def test_an_unknown_suite_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown suite"):
        mutate.load_catalogue(catalogue(tmp_path, [mutant(catches=["smoke"])]))


def test_two_mutants_with_one_name_are_refused(tmp_path):
    with pytest.raises(ValueError, match="share a name"):
        mutate.load_catalogue(catalogue(tmp_path, [mutant(), mutant()]))


@pytest.mark.parametrize(
    "source, problem", [("return False\n", "found 0 times"), ("return True\nreturn True\n", "found 2 times")]
)
def test_an_anchor_that_does_not_appear_exactly_once_is_stale(tmp_path, source, problem):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rule.py").write_text(source, encoding="utf-8")

    stale = mutate.stale_anchors(tmp_path, mutate.load_catalogue(catalogue(tmp_path, [mutant()])))

    assert len(stale) == 1 and problem in stale[0]


def test_a_mutant_is_undone_even_when_its_suite_blows_up(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    rule = tmp_path / "app" / "rule.py"
    rule.write_text("return True\n", encoding="utf-8")
    monkeypatch.setattr(mutate.ProductServer, "start", lambda self: True)
    monkeypatch.setattr(mutate.ProductServer, "stop", lambda self: None)

    def explode(name):
        assert rule.read_text() == "return False\n", "the suite must run against the mutated file"
        raise RuntimeError("suite crashed")

    monkeypatch.setattr(mutate, "run_suite", explode)

    with pytest.raises(RuntimeError):
        mutate.run_mutant(tmp_path, mutate.load_catalogue(catalogue(tmp_path, [mutant()]))[0], Path("python"))
    assert rule.read_text() == "return True\n"


@pytest.mark.parametrize("passes, caught", [(False, "api"), (True, None)])
def test_a_failing_suite_catches_the_mutant_and_a_passing_one_lets_it_survive(
    tmp_path, monkeypatch, passes, caught
):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rule.py").write_text("return True\n", encoding="utf-8")
    monkeypatch.setattr(mutate.ProductServer, "start", lambda self: True)
    monkeypatch.setattr(mutate.ProductServer, "stop", lambda self: None)
    monkeypatch.setattr(mutate, "run_suite", lambda name: (passes, "FAILED tests/x.py::t"))

    outcome = mutate.run_mutant(
        tmp_path, mutate.load_catalogue(catalogue(tmp_path, [mutant()]))[0], Path("python")
    )

    assert outcome.caught_by == caught


def test_a_mutant_the_product_cannot_even_start_with_counts_as_caught(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rule.py").write_text("return True\n", encoding="utf-8")
    monkeypatch.setattr(mutate.ProductServer, "start", lambda self: False)
    monkeypatch.setattr(mutate.ProductServer, "stop", lambda self: None)

    outcome = mutate.run_mutant(
        tmp_path, mutate.load_catalogue(catalogue(tmp_path, [mutant()]))[0], Path("python")
    )

    assert outcome.caught_by == "startup"


def test_the_export_is_the_last_commit_and_never_the_working_tree(tmp_path):
    repo = tmp_path / "product"
    repo.mkdir()
    run = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    (repo / "rule.py").write_text("committed\n")
    run("add", "rule.py")
    run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "one")
    (repo / "rule.py").write_text("uncommitted edit\n")

    workspace, commit = mutate.export_head(repo)
    try:
        assert (workspace / "rule.py").read_text() == "committed\n"
        assert (repo / "rule.py").read_text() == "uncommitted edit\n", "the checkout is never written to"
        assert commit
    finally:
        shutil.rmtree(workspace)


def test_only_committed_development_values_are_read_never_a_private_env(tmp_path):
    (tmp_path / ".env.example").write_text("# a comment\nSECRET_KEY=dev\n\nSEED_OWNER_PASSWORD=x=y\n")
    (tmp_path / ".env").write_text("SECRET_KEY=someones-real-key\n")

    assert mutate.env_example(tmp_path) == {"SECRET_KEY": "dev", "SEED_OWNER_PASSWORD": "x=y"}
