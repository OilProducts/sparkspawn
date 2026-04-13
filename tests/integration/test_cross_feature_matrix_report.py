from __future__ import annotations

import json

import pytest

from tests.support.cross_feature_matrix import (
    CROSS_FEATURE_MATRIX_ROWS,
    assert_cross_feature_matrix_passes,
    run_cross_feature_matrix,
)


def test_cross_feature_matrix_executes_and_persists_report(tmp_path) -> None:
    report_path = tmp_path / "cross-feature-matrix-report.json"

    report = run_cross_feature_matrix(report_path)

    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["summary"]["total"] == len(CROSS_FEATURE_MATRIX_ROWS)
    assert report["summary"]["passed"] + report["summary"]["failed"] == len(CROSS_FEATURE_MATRIX_ROWS)
    assert [row["name"] for row in report["rows"]] == CROSS_FEATURE_MATRIX_ROWS


def test_cross_feature_matrix_fails_when_any_row_is_unchecked() -> None:
    report = {
        "rows": [
            {"name": CROSS_FEATURE_MATRIX_ROWS[0], "pass": True},
            {"name": CROSS_FEATURE_MATRIX_ROWS[1], "pass": False},
        ]
    }

    with pytest.raises(RuntimeError, match="failing or missing"):
        assert_cross_feature_matrix_passes(report)


def test_cross_feature_matrix_allows_all_checked_rows() -> None:
    report = {"rows": [{"name": name, "pass": True} for name in CROSS_FEATURE_MATRIX_ROWS]}

    assert_cross_feature_matrix_passes(report)
