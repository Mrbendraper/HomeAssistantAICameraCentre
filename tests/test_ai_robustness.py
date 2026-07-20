"""Tests for AI-failure handling: parsing, transient-error classification,
and the failure-count sensor.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.ai_camera_centre.analyzer import (
    _is_transient_error,
    _parse_ai_result,
)
from custom_components.ai_camera_centre.sensor import CameraAnalysisFailures


# -- fix #2: a missing/garbage score is a failure, not a benign score 1 -----


def test_missing_score_raises() -> None:
    with pytest.raises(HomeAssistantError, match="missing suspicious_index"):
        _parse_ai_result({"short": "someone at the gate"})


def test_non_numeric_score_raises() -> None:
    with pytest.raises(HomeAssistantError, match="non-numeric"):
        _parse_ai_result({"suspicious_index": "not a number"})


def test_valid_score_parses_and_clamps() -> None:
    assert _parse_ai_result({"suspicious_index": 7})["score"] == 7
    assert _parse_ai_result({"suspicious_index": 42})["score"] == 10
    assert _parse_ai_result({"suspicious_index": 0})["score"] == 1


# -- fix #1: transient vs structure-unsupported classification --------------


@pytest.mark.parametrize(
    "message",
    [
        "503 Service Unavailable",
        "This model is currently experiencing high demand",
        "UNAVAILABLE",
        "429 rate limit exceeded",
        "Deadline exceeded",
        "The request timed out",
    ],
)
def test_transient_errors_are_detected(message: str) -> None:
    assert _is_transient_error(Exception(message)) is True


@pytest.mark.parametrize(
    "message",
    [
        "response_schema is not supported by this model",
        "structured output unsupported",
        "Invalid schema",
    ],
)
def test_capability_errors_are_not_transient(message: str) -> None:
    # Errs toward non-transient so a genuine unsupported-structure error still
    # falls back to text parsing.
    assert _is_transient_error(Exception(message)) is False


# -- the failure-count sensor -----------------------------------------------


def _failure_sensor() -> CameraAnalysisFailures:
    pipeline = SimpleNamespace(camera_id="back_garden", label="Back Garden")
    sensor = CameraAnalysisFailures(pipeline)
    # _on_failure writes state; bypass the HA entity machinery in this unit test.
    sensor.async_write_ha_state = lambda: None
    return sensor


def test_failure_sensor_counts_only_its_own_camera() -> None:
    sensor = _failure_sensor()
    assert sensor.native_value == 0

    sensor._on_failure("back_garden")
    sensor._on_failure("back_garden")
    assert sensor.native_value == 2

    # Another camera's failure must not tick this one.
    sensor._on_failure("front_garden")
    assert sensor.native_value == 2


def test_failure_sensor_is_a_statistics_counter() -> None:
    from homeassistant.components.sensor import SensorStateClass

    sensor = _failure_sensor()
    # TOTAL_INCREASING is what gives it long-term statistics (day/week/month).
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
