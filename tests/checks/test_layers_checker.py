"""check_layers.py: import collection and allow-list enforcement."""
from __future__ import annotations

import textwrap

import pytest

OK_FILES = {
    "fakepkg/low/color.py": "from __future__ import annotations\nimport json\n",
    "fakepkg/low/util.py": textwrap.dedent("""\
        from typing import TYPE_CHECKING
        from . import color
        from .color import json as _j
        from fakepkg import __version__
        from .. import __version__ as v2
        if TYPE_CHECKING:
            from fakepkg.low.color import thing
        def f():
            import json
        """),
    "fakepkg/low/special/deep.py": "import os\nfrom ..color import x\nfrom ... import low\n",
    "fakepkg/high/mode.py": textwrap.dedent("""\
        import importlib
        from fakepkg.low import color
        from ..low import color as c2
        mod = importlib.import_module("json")
        """),
    "fakepkg/app/main.py": textwrap.dedent("""\
        import os
        import importlib
        import fakepkg
        from fakepkg import high, low
        from fakepkg.high import mode
        from .. import app
        def load(name):
            return importlib.import_module(name)
        """),
}


def run(layers_mod, root, cfg, capsys):
    code = layers_mod.run(root, cfg)
    return code, capsys.readouterr().out


def test_clean_package_passes(layers_mod, fake_repo, capsys):
    root, cfg = fake_repo(OK_FILES)
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 0, out
    assert out.startswith("check_layers: OK (")
    assert "10 files" in out


# (source placed in fakepkg/low/bad.py, expected line, expected fragment)
VIOLATIONS = {
    "plain": ("import json\nimport os\n", 2, "imports 'os'"),
    "dotted": ("import os.path\n", 1, "imports 'os.path'"),
    "from": ("from os import path\n", 1, "imports 'os'"),
    "relative_up": ("from ..high import mode\n", 1, "imports 'fakepkg.high'"),
    "relative_root_name": ("from .. import high\n", 1, "imports 'fakepkg.high'"),
    "absolute_higher": ("from fakepkg.high.mode import x\n", 1,
                        "imports 'fakepkg.high.mode'"),
    "import_higher": ("import fakepkg.app.main\n", 1, "imports 'fakepkg.app.main'"),
    "root_package": ("import fakepkg\n", 1, "imports 'fakepkg'"),
    "root_non_version": ("from fakepkg import __version__, helper\n", 1,
                         "imports 'fakepkg.helper'"),
    "nested_function": ("def f():\n    if True:\n        import os\n", 3, "imports 'os'"),
    "class_body": ("class A:\n    import os\n", 2, "imports 'os'"),
    "try_except": ("try:\n    import json\nexcept ImportError:\n    import os\n", 4,
                   "imports 'os'"),
    "type_checking": ("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n"
                      "    from fakepkg.high import mode\n", 3, "imports 'fakepkg.high'"),
    "import_module_literal": ("x = importlib.import_module('os')\n", 1, "imports 'os'"),
    "import_module_bare": ("x = import_module('fakepkg.high')\n", 1,
                           "imports 'fakepkg.high'"),
    "import_module_relative": ("x = import_module('..high')\n", 1,
                               "imports 'fakepkg.high'"),
    "dunder_import_literal": ("x = __import__('os')\n", 1, "imports 'os'"),
    "dunder_import_kw": ("x = __import__(name='os')\n", 1, "imports 'os'"),
    "dynamic_non_literal": ("name = 'os'\nx = __import__(name)\n", 2, "non-literal"),
    "dynamic_fstring": ("x = importlib.import_module(f'{1}')\n", 1, "non-literal"),
    "brand_new_library": ("import brandnewlib\n", 1, "imports 'brandnewlib'"),
    "unlisted_stdlib": ("import itertools\n", 1, "imports 'itertools'"),
    "beyond_root": ("from .... import x\n", 1, "beyond the package root"),
}


@pytest.mark.parametrize("case", sorted(VIOLATIONS))
def test_violation_detected(layers_mod, fake_repo, capsys, case):
    source, line, fragment = VIOLATIONS[case]
    root, cfg = fake_repo({**OK_FILES, "fakepkg/low/bad.py": source})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 1, out
    lines = [ln for ln in out.splitlines() if ln.startswith("fakepkg/")]
    assert len(lines) == 1, out
    assert lines[0].startswith(f"fakepkg/low/bad.py:{line}: [low] "), out
    assert fragment in lines[0]


def test_message_format(layers_mod, fake_repo, capsys):
    root, cfg = fake_repo({"fakepkg/low/bad.py": "import brandnewlib\n"})
    _, out = run(layers_mod, root, cfg, capsys)
    assert "fakepkg/low/bad.py:1: [low] imports 'brandnewlib' (not allowed)" in out
    assert "1 violation(s)" in out


def test_longest_prefix_wins(layers_mod, fake_repo, capsys):
    # os is allowed in low/special but not in low.
    root, cfg = fake_repo({"fakepkg/low/special/x.py": "import os\n",
                           "fakepkg/low/y.py": "import os\n"})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 1
    assert "fakepkg/low/y.py:1: [low]" in out
    assert "special/x.py" not in out


def test_non_literal_dynamic_import_allowed_in_app(layers_mod, fake_repo, capsys):
    root, cfg = fake_repo({"fakepkg/app/x.py": "import importlib\n"
                                               "m = importlib.import_module(n)\n"})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 0, out


def test_unassigned_file_fails(layers_mod, fake_repo, capsys):
    root, cfg = fake_repo({"fakepkg/stray.py": "", "fakepkg/other/mod.py": "",
                           "fakepkg/lowish.py": ""})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 1
    # "fakepkg/low" must not claim "fakepkg/lowish.py": prefixes match whole segments.
    assert "fakepkg/lowish.py:1: file is not assigned to any layer" in out
    assert "fakepkg/stray.py:1: file is not assigned to any layer" in out
    assert "fakepkg/other/mod.py:1: file is not assigned to any layer" in out


def test_import_of_unassigned_internal_module_fails(layers_mod, fake_repo, capsys):
    root, cfg = fake_repo({"fakepkg/app/x.py": "import fakepkg.nowhere.thing\n"})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 1
    assert "[app] imports 'fakepkg.nowhere.thing' (not allowed)" in out


def test_syntax_error_reported(layers_mod, fake_repo, capsys):
    root, cfg = fake_repo({"fakepkg/low/broken.py": "def (:\n"})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 1
    assert "fakepkg/low/broken.py:1: syntax error" in out


def test_every_violation_in_a_file_is_reported(layers_mod, fake_repo, capsys):
    src = "import os\nimport sys\ndef f():\n    import fakepkg.high\n"
    root, cfg = fake_repo({"fakepkg/low/bad.py": src})
    code, out = run(layers_mod, root, cfg, capsys)
    assert code == 1
    for n in (1, 2, 4):
        assert f"fakepkg/low/bad.py:{n}: [low]" in out
    assert "3 violation(s)" in out
