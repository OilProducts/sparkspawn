from __future__ import annotations

import json

from attractor.parity_matrix import CROSS_FEATURE_PARITY_MATRIX_ROWS, run_cross_feature_parity_matrix


def test_cross_feature_parity_matrix_executes_and_persists_report(tmp_path) -> None:
    report_path = tmp_path / "parity-matrix-report.json"

    report = run_cross_feature_parity_matrix(report_path)

    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["summary"]["total"] == len(CROSS_FEATURE_PARITY_MATRIX_ROWS)
    assert report["summary"]["passed"] + report["summary"]["failed"] == len(CROSS_FEATURE_PARITY_MATRIX_ROWS)
    assert [row["name"] for row in report["rows"]] == CROSS_FEATURE_PARITY_MATRIX_ROWS
