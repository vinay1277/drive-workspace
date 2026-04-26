"""Shared pytest fixtures for the reference-server suite.

Every test in this directory hits the Flask app via
``Flask.test_client()`` — no real network, no subprocess. Each test
gets a freshly-created app so the in-memory ``_sessions`` dict and
its ``threading.Lock`` start clean and tests cannot pollute each
other across the module.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient

from reference_server.app import create_app


@pytest.fixture
def client() -> Iterator[FlaskClient]:
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c
