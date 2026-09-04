"""Unit tests for core. NOT the --help snapshot the doctrine requires --
that is the gap this fixture exists to make visible."""

import pytest

from widgetctl import core


def test_describe_finds_widget():
    assert core.describe([{"id": "a"}], "a") == {"id": "a"}


def test_describe_raises_when_absent():
    with pytest.raises(core.WidgetNotFound):
        core.describe([], "a")
