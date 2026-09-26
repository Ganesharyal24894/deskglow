"""check.py: step list, run-everything aggregation and exit codes.

Sub-steps are tiny `python -c` commands; the real pytest suite is never run
from here.
"""
from __future__ import annotations

import sys


def py(code: str) -> list:
    return [sys.executable, "-c", code]


def touch(path) -> str:
    return f"open({str(path)!r}, 'w').close()"


def test_all_steps_run_even_after_a_failure(check_mod, tmp_path, capsys):
    steps = [
        check_mod.Step("first", py(touch(tmp_path / "1") + "; raise SystemExit(1)")),
        check_mod.Step("second", py(touch(tmp_path / "2"))),
        check_mod.Step("third", py(touch(tmp_path / "3") + "; raise SystemExit(3)")),
    ]
    results = check_mod.run_steps(steps, tmp_path)
    assert [(r.name, r.status) for r in results] == [
        ("first", "FAIL"), ("second", "PASS"), ("third", "FAIL")]
    assert all((tmp_path / n).exists() for n in "123")
    assert "exit 3" in results[2].detail
    assert check_mod.summarise(results) == 1
    out = capsys.readouterr().out
    assert "check: FAILED (first, third)" in out


def test_all_pass_exits_zero(check_mod, tmp_path, capsys):
    steps = [check_mod.Step("a", py("pass")), check_mod.Step("b", py("print('hi')"))]
    assert check_mod.summarise(check_mod.run_steps(steps, tmp_path)) == 0
    assert "check: all steps passed" in capsys.readouterr().out


def test_skipped_step_is_visible_and_not_a_failure(check_mod, tmp_path, capsys):
    steps = [check_mod.Step("presets", None, "not present"),
             check_mod.Step("ok", py("pass"))]
    results = check_mod.run_steps(steps, tmp_path)
    step_out = capsys.readouterr().out
    assert "=== presets ===\nSKIPPED (not present)" in step_out
    assert results[0].status == "SKIPPED"
    assert check_mod.summarise(results) == 0
    assert "presets  SKIPPED (not present)" in capsys.readouterr().out


def test_unstartable_command_is_a_failure(check_mod, tmp_path, capsys):
    steps = [check_mod.Step("ghost", [str(tmp_path / "no-such-binary")])]
    results = check_mod.run_steps(steps, tmp_path)
    assert results[0].status == "FAIL"
    assert check_mod.summarise(results) == 1


def test_steps_run_in_given_cwd(check_mod, tmp_path):
    steps = [check_mod.Step("cwd", py("import os; open('here', 'w').close()"))]
    check_mod.run_steps(steps, tmp_path)
    assert (tmp_path / "here").exists()


def test_build_steps_order_and_interpreter(check_mod, tmp_path):
    steps = check_mod.build_steps(tmp_path)
    assert [s.name for s in steps] == ["line limit", "layers", "presets", "ruff", "pytest"]
    for step in steps:
        if step.cmd is not None:
            assert step.cmd[0] == sys.executable
    by_name = {s.name: s for s in steps}
    assert by_name["ruff"].cmd[1:] == ["-m", "ruff", "check", "."]
    assert by_name["pytest"].cmd[1:] == ["-m", "pytest", "-q"]
    assert by_name["presets"].cmd is None
    assert by_name["presets"].skip_reason == "not present"


def test_build_steps_uses_gen_presets_when_present(check_mod, tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/gen_presets.py").write_text("", encoding="utf-8")
    by_name = {s.name: s for s in check_mod.build_steps(tmp_path)}
    cmd = by_name["presets"].cmd
    assert cmd[0] == sys.executable
    assert cmd[1].endswith("gen_presets.py")
    assert cmd[2:] == ["--check"]


def test_fast_skips_pytest(check_mod, tmp_path):
    by_name = {s.name: s for s in check_mod.build_steps(tmp_path, fast=True)}
    assert by_name["pytest"].cmd is None
    assert by_name["ruff"].cmd is not None


def test_main_aggregates_and_passes_fast(check_mod, monkeypatch, tmp_path, capsys):
    seen = {}

    def fake_build(root, fast=False):
        seen["fast"] = fast
        return [check_mod.Step("bad", py("raise SystemExit(2)")),
                check_mod.Step("good", py("pass"))]

    monkeypatch.setattr(check_mod, "build_steps", fake_build)
    monkeypatch.setattr(check_mod, "ROOT", tmp_path)
    assert check_mod.main(["--fast"]) == 1
    assert seen["fast"] is True
    out = capsys.readouterr().out
    assert "bad" in out and "FAIL" in out and "PASS" in out
