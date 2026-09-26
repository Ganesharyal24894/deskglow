"""check_lines.py: the 200-line limit."""
from __future__ import annotations

import subprocess
import sys

from checks_support import SCRIPTS_DIR, write_tree


def src(n: int) -> str:
    return "x = 1\n" * n


def test_files_at_limit_pass(lines_mod, tmp_path, capsys):
    write_tree(tmp_path, {"deskglow/a.py": src(200), "tests/t.py": src(10),
                          "scripts/s.py": "", "tools/t.py": src(199)})
    assert lines_mod.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "check_lines: OK (4 files, limit 200)" in out


def test_over_limit_fails_listing_path_and_count(lines_mod, tmp_path, capsys):
    write_tree(tmp_path, {"deskglow/sub/big.py": src(201), "deskglow/ok.py": src(3),
                          "tools/huge.py": src(350)})
    assert lines_mod.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "deskglow/sub/big.py:201" in out
    assert "tools/huge.py:350" in out
    assert "ok.py" not in out


def test_each_default_root_is_checked(lines_mod, tmp_path):
    for rel in ("deskglow/x.py", "tests/x.py", "scripts/x.py", "tools/x.py",
                "hatch_build.py"):
        write_tree(tmp_path, {rel: src(201)})
        bad, _ = lines_mod.find_violations(tmp_path, list(lines_mod.DEFAULT_PATHS), 200)
        assert bad == [f"{rel}:201"]
        (tmp_path / rel).unlink()


def test_unlisted_dirs_and_non_python_ignored(lines_mod, tmp_path, capsys):
    write_tree(tmp_path, {"docs/big.py": src(500), "deskglow/data.json": src(500),
                          "setup.py": src(500)})
    assert lines_mod.main(["--root", str(tmp_path)]) == 0


def test_skipped_directories(lines_mod, tmp_path):
    write_tree(tmp_path, {"deskglow/__pycache__/a.py": src(300),
                          "tools/.venv/lib/b.py": src(300),
                          "tests/.hidden/c.py": src(300),
                          "tests/real.py": src(201)})
    bad, checked = lines_mod.find_violations(tmp_path, list(lines_mod.DEFAULT_PATHS), 200)
    assert bad == ["tests/real.py:201"]
    assert checked == 1


def test_crlf_and_missing_final_newline_counted_correctly(lines_mod, tmp_path):
    (tmp_path / "deskglow").mkdir()
    (tmp_path / "deskglow/a.py").write_bytes(b"x = 1\r\n" * 200 + b"y = 2")
    bad, _ = lines_mod.find_violations(tmp_path, ["deskglow"], 200)
    assert bad == ["deskglow/a.py:201"]


def test_custom_limit_and_paths(lines_mod, tmp_path, capsys):
    write_tree(tmp_path, {"pkg/a.py": src(11), "deskglow/b.py": src(500)})
    assert lines_mod.main(["--root", str(tmp_path), "--limit", "10", "pkg"]) == 1
    out = capsys.readouterr().out
    assert "pkg/a.py:11" in out
    assert "deskglow" not in out
    assert lines_mod.main(["--root", str(tmp_path), "--limit", "11", "pkg"]) == 0


def test_cli_exit_code(tmp_path):
    write_tree(tmp_path, {"scripts/a.py": src(201)})
    proc = subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_lines.py"),
                           "--root", str(tmp_path)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1
    assert "scripts/a.py:201" in proc.stdout
