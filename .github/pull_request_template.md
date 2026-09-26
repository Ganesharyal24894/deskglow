## What this changes

<!-- A short description of the change and why it's needed. -->

## Related issue

<!-- e.g. Fixes #123 -->

## How it was tested

<!--
What you ran, and on what. If you tested against a real strip, say which
controller. If the change is hardware-only, explain how the automated tests
cover the logic around it.
-->

## Checklist

- [ ] Includes a regression test that **failed before the fix** and passes after it
      (required for any bug fix — see [CONTRIBUTING.md](../CONTRIBUTING.md))
- [ ] New tests do **not** require a real strip, a Bluetooth adapter, an X server
      or an audio device (anything that does is marked `@pytest.mark.hardware`)
- [ ] `python -m pytest -q -m "not hardware"` passes locally
- [ ] `ruff check .` passes locally
- [ ] `python scripts/check.py` passes locally (line limit, layers, presets, lint, tests)
- [ ] If a preset changed: `python scripts/gen_presets.py` was run and `presets_gen.py` committed
- [ ] Public behaviour changes are reflected in `README.md`
- [ ] `CHANGELOG.md` has an entry under `## [Unreleased]`
- [ ] No new runtime dependency (or, if there is one, it's justified below and
      added to the right optional extra rather than the core install)

## Notes for the reviewer

<!-- Anything you're unsure about, trade-offs you made, follow-ups you left. -->
