"""
Integration-style FMI test using the Feedthrough.fmu fixture.

This exercises the runner against a real FMU (no network, local file copy). It
monkeypatches download_file to copy the fixture into the working directory,
builds a typed FMIInputEnvelope, and asserts the output echoes the input for
the known feedthrough variable.
"""

from __future__ import annotations

import platform
import shutil
from pathlib import Path

import pytest
from validators.fmi import runner

from vb_shared.fmi.envelopes import FMIInputEnvelope, FMIInputs, FMIOutputEnvelope
from vb_shared.validations.envelopes import ExecutionContext, InputFileItem, SupportedMimeType


@pytest.mark.integration
def test_feedthrough_fmu_echoes_input(monkeypatch, tmp_path) -> None:
    """Run Feedthrough.fmu and assert Int32_output matches Int32_input."""
    if platform.system().lower() == "darwin" and platform.machine().lower().startswith("arm"):
        pytest.skip("Feedthrough.fmu fixture is x86_64-only; skip on Apple Silicon.")

    fixture = Path(__file__).parent / "assets" / "Feedthrough.fmu"
    assert fixture.exists(), "Feedthrough.fmu fixture missing"

    def _fake_download(uri: str, dest: Path) -> None:
        shutil.copy(Path(uri), dest)

    monkeypatch.setattr("validators.fmi.runner.download_file", _fake_download)

    envelope = FMIInputEnvelope(
        run_id="test-run",
        validator={"id": "1", "type": "fmi", "version": "1"},
        org={"id": "1", "name": "Test Org"},
        workflow={"id": "1", "step_id": "1", "step_name": "Feedthrough"},
        input_files=[
            InputFileItem(
                name="model.fmu",
                mime_type=SupportedMimeType.FMU,
                role="fmu",
                uri=str(fixture),
            )
        ],
        inputs=FMIInputs(
            input_values={"Int32_input": 5},
            output_variables=["Int32_output"],
        ),
        context=ExecutionContext(
            callback_url="http://example.com",
            execution_bundle_uri=str(tmp_path),
        ),
    )

    outputs, _ = runner.run_fmi_simulation(envelope)
    assert isinstance(outputs, FMIOutputEnvelope.__fields__["outputs"].type_)  # type: ignore[attr-defined]
    assert outputs.output_values["Int32_output"] == pytest.approx(5)
