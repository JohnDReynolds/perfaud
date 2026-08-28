# Maintenance

Create the development environment and run the routine gate:

```bash
python -m venv .venv
./.venv/bin/python -m pip install -e '.[dev]'
./.venv/bin/python scripts/check_project.py
```

The project gate runs tests, typing, lint errors, documentation and image drift,
direct universal-wheel inspection, and installed-wheel workflow smokes. The release
candidate adds demo-health checks and the unchanged 500x scale gate:

```bash
./.venv/bin/python scripts/check_release_candidate.py
```

Regenerate and verify the single marketing image with:

```bash
./.venv/bin/python scripts/render_readme_images.py
./.venv/bin/python scripts/render_readme_images.py --check
```

Build only the direct wheel; there is no sdist or wheel-from-sdist release path:

```bash
./.venv/bin/python -m build --wheel
./.venv/bin/python -m twine check dist/*.whl
```

Never weaken financial invariants, tolerances, row limits, warning boundaries,
failure boundaries, or the 500x gate to obtain a passing result. Investigate the
implementation first.
