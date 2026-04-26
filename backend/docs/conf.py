"""Sphinx configuration for drive_workspace API docs.

Build locally with::

    pip install -e .[docs]
    cd backend/docs
    sphinx-build -b html . _build

Output lands in ``backend/docs/_build/html/``; ``.gitignore`` covers it.

Decisions baked in here:

- **Docstring style: Google.** Less verbose than NumPy for the
  short methods that dominate this package; ``sphinx-autodoc2``
  recognises Google-style ``Args``, ``Returns``, ``Raises``, and
  ``Attributes`` sections natively.
- **Modern autodoc via sphinx-autodoc2.** PEP 604 union types
  (``X | Y``), ``Protocol`` classes, and ``TypedDict`` render
  cleanly without the classic ``napoleon`` + ``autodoc`` pairing.
- **Markdown source via myst-parser.** Authored docs (this index,
  future how-to pages) live in ``.md``; autodoc2 still emits
  ``.rst`` under the hood for the API reference.
- **Warnings, not errors.** Phase 3 hardens to ``sphinx-build -W``
  and adds a CI step; until then this build tolerates missing
  docstrings on internal symbols. See ``docs/plan.md``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

# -- Project metadata ---------------------------------------------------

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = tomllib.loads((_BACKEND_ROOT / "pyproject.toml").read_text())

project = _PYPROJECT["project"]["name"]
release = _PYPROJECT["project"]["version"]
version = release
author = "drive-workspace authors"
copyright = f"2026, {author}"

# -- General configuration ---------------------------------------------

extensions = [
    "myst_parser",
    "autodoc2",
]

# autodoc2: point at the package source. Path is relative to conf.py.
autodoc2_packages = [
    {
        "path": "../drive_workspace",
        "auto_mode": True,
    },
]

# Tests aren't part of the public API surface — skip the modules
# (and their fixtures) so the rendered reference shows production
# code only. Internal `_fixtures` subpackage is excluded by the
# leading-underscore rule below; the explicit pattern here covers
# the test files themselves.
autodoc2_skip_module_regexes = [
    r"drive_workspace\.tests(\..*)?",
]

# Render docstrings as Markdown (myst) so Google-style sections survive
# the autodoc2 → MyST → HTML pipeline without a second translation pass.
autodoc2_render_plugin = "myst"

# Hide internal-only symbols from the generated reference. Anything
# under ``adapters/``, ``stores/``, or ``tests/`` whose name starts
# with ``_`` is implementation detail.
autodoc2_hidden_objects = ["dunder", "private", "inherited"]

# Don't fail the build on missing references — Phase 3 hardening will
# enable nitpicky mode and address real gaps.
nitpicky = False

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "smartquotes",
]

# Source suffixes — let myst handle .md, default to .rst for autodoc2's
# generated stubs.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML output -------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path: list[str] = []  # add when we have logos / custom CSS
html_title = f"{project} {release}"
