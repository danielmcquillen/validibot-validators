"""Unit tests for EnergyPlus container helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from validators.energyplus import runner
from validators.energyplus.main import (
    _infer_artifact_type,
    _rewrite_output_paths,
)
from vb_shared.energyplus.envelopes import EnergyPlusOutputs
from vb_shared.energyplus.models import (
    EnergyPlusSimulationLogs,
    EnergyPlusSimulationMetrics,
    EnergyPlusSimulationOutputs,
)
from vb_shared.validations.envelopes import ValidationArtifact


def test_infer_artifact_type() -> None:
    """Artifact typing should detect common EnergyPlus outputs."""
    assert _infer_artifact_type("eplusout.sql") == "simulation-db"
    assert _infer_artifact_type("results.csv") == "timeseries-csv"
    assert _infer_artifact_type("eplusout.err") == "err-log"
    assert _infer_artifact_type("other.bin") == "file"


def test_rewrite_output_paths_prefers_gcs_uris() -> None:
    """Output paths should be rewritten to uploaded GCS URIs when available."""
    artifacts = [
        ValidationArtifact(
            name="eplusout.sql",
            type="simulation-db",
            mime_type="application/x-sqlite3",
            uri="gs://bucket/run/outputs/eplusout.sql",
            size_bytes=123,
        ),
        ValidationArtifact(
            name="eplusout.err",
            type="err-log",
            mime_type="text/plain",
            uri="gs://bucket/run/outputs/eplusout.err",
            size_bytes=42,
        ),
    ]

    outputs = EnergyPlusOutputs(
        outputs=EnergyPlusSimulationOutputs(
            eplusout_sql=Path("/tmp/eplusout.sql"),
            eplusout_err=Path("/tmp/eplusout.err"),
        ),
        metrics=EnergyPlusSimulationMetrics(),
        logs=EnergyPlusSimulationLogs(),
        energyplus_returncode=0,
        execution_seconds=1.0,
        invocation_mode="cli",
    )

    rewritten = _rewrite_output_paths(outputs, artifacts)

    assert str(rewritten.outputs.eplusout_sql) == "gs://bucket/run/outputs/eplusout.sql"
    assert str(rewritten.outputs.eplusout_err) == "gs://bucket/run/outputs/eplusout.err"


def test_extract_metrics_reads_tabular_data(tmp_path) -> None:
    """_extract_metrics should pull electricity, gas, and area from SQL tables."""
    sql_path = tmp_path / "eplusout.sql"
    conn = sqlite3.connect(sql_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE TabularData (
            ReportName TEXT, TableName TEXT, RowName TEXT, ColumnName TEXT, Value TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE TabularDataWithStrings (
            ReportName TEXT, TableName TEXT, RowName TEXT, ColumnName TEXT, Value TEXT
        )
        """
    )
    rows = [
        (
            "AnnualBuildingUtilityPerformanceSummary",
            "End Uses",
            "Total End Uses",
            "Electricity [kWh]",
            "100",
        ),
        (
            "AnnualBuildingUtilityPerformanceSummary",
            "End Uses",
            "Total End Uses",
            "Natural Gas [kWh]",
            "50",
        ),
        ("Entire Facility", "Building Area", "Total Building Area", "Area", "25"),
    ]
    cur.executemany(
        "INSERT INTO TabularData VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    cur.executemany(
        "INSERT INTO TabularDataWithStrings VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    metrics = runner._extract_metrics(sql_path)  # type: ignore[attr-defined]
    assert metrics.electricity_kwh == 100
    assert metrics.natural_gas_kwh == 50
    assert metrics.energy_use_intensity_kwh_m2 == 4
