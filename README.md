# Validators

This directory contains validator containers for running advanced validations (EnergyPlus simulations, FMU execution, etc.). Validators can run in two modes:

1. **GCP Cloud Run Jobs** (production): Async execution with GCS storage and callbacks
2. **Self-hosted Docker** (self-hosted): Sync execution with local filesystem storage

## Architecture Overview

### GCP Mode (Cloud Run Jobs)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Cloud Run Service (Django)                                          │
│                                                                     │
│ 1. Creates ValidationInputEnvelope                                  │
│ 2. Uploads to GCS as input.json                                     │
│ 3. Triggers Cloud Run Job via Cloud Tasks                           │
│ 4. Receives callback when complete                                  │
│ 5. Downloads output.json from GCS                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Cloud Run Job (Validator Container)                                 │
│                                                                     │
│ 1. Downloads input.json from GCS (gs://)                            │
│ 2. Deserializes to typed envelope (e.g., EnergyPlusInputEnvelope)   │
│ 3. Runs validation/simulation                                       │
│ 4. Creates typed output envelope (e.g., EnergyPlusOutputEnvelope)   │
│ 5. Uploads output.json to GCS                                       │
│ 6. POSTs minimal callback to Django                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Self-Hosted Mode (Docker)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Django (Dramatiq Worker)                                            │
│                                                                     │
│ 1. Creates ValidationInputEnvelope                                  │
│ 2. Writes to local storage as input.json                            │
│ 3. Runs Docker container SYNCHRONOUSLY (blocks until complete)      │
│ 4. Reads output.json from local storage                             │
│ 5. Processes results immediately                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Docker Container (Validator)                                        │
│                                                                     │
│ 1. Reads input.json from local storage (file://)                    │
│ 2. Deserializes to typed envelope                                   │
│ 3. Runs validation/simulation                                       │
│ 4. Creates typed output envelope                                    │
│ 5. Writes output.json to local storage                              │
│ 6. Exits (no callback needed - sync execution)                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
vb_validators/
├── justfile                  # Build/deploy commands
├── pyproject.toml           # Python project config
└── validators/
    ├── core/                # Shared utilities for all validators
    │   ├── storage_client.py    # Storage I/O (gs:// and file://)
    │   ├── gcs_client.py        # Legacy alias for storage_client
    │   ├── callback_client.py   # HTTP callback utilities
    │   └── envelope_loader.py   # Envelope serialization helpers
    │
    ├── energyplus/          # EnergyPlus validator container
    │   ├── Dockerfile
    │   ├── __metadata__.py  # Validator metadata
    │   ├── main.py          # Container entrypoint
    │   ├── runner.py        # EnergyPlus execution logic
    │   ├── requirements.txt
    │   └── tests/
    │
    └── fmi/                 # FMI/FMU simulation validator
        ├── Dockerfile
        ├── __metadata__.py  # Validator metadata
        ├── main.py
        ├── runner.py
        ├── requirements.txt
        └── tests/
```

## Environment Variables

Validators accept input via environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `VALIDIBOT_INPUT_URI` | Yes* | Storage URI to input envelope (gs:// or file://) |
| `VALIDIBOT_OUTPUT_URI` | No | Storage URI for output (derived from input if not set) |
| `INPUT_URI` | Yes* | Alias for VALIDIBOT_INPUT_URI (backwards compat) |

*One of `VALIDIBOT_INPUT_URI` or `INPUT_URI` must be set, or URI passed as first CLI argument.

The loader checks in this order:
1. `VALIDIBOT_INPUT_URI` (preferred for self-hosted Docker)
2. `INPUT_URI` (for Cloud Run Jobs / backwards compatibility)
3. First command-line argument (for manual testing)

## Storage Backends

Validators support two storage backends:

- **`gs://`** - Google Cloud Storage (production)
- **`file://`** - Local filesystem (self-hosted)

Examples:
```
gs://my-bucket/runs/org-123/run-456/input.json
file:///app/storage/private/runs/org-123/run-456/input.json
```

## Validator Metadata

Each validator includes a `__metadata__.py` file with standardized information:

```python
from validators.energyplus.__metadata__ import get_metadata

metadata = get_metadata()
# Returns:
# {
#     "validator_type": "ENERGYPLUS",
#     "validator_name": "EnergyPlus Simulation Validator",
#     "image_name": "validibot-validator-energyplus",
#     "env_vars": {...},
#     "supported_input_types": [...],
#     "resource_requirements": {...},
#     ...
# }
```

## Validator Container Contract

Each validator container MUST:

1. **Receive input location** via environment variable or CLI argument

2. **Load input envelope** from storage:
   ```python
   from validators.core.envelope_loader import load_input_envelope
   from vb_shared.energyplus.envelopes import EnergyPlusInputEnvelope

   input_envelope = load_input_envelope(EnergyPlusInputEnvelope)
   ```

3. **Run validation/simulation**:
   - Use typed configuration from `input_envelope.inputs`
   - Download input files from URIs in `input_envelope.input_files`
   - Execute domain-specific logic

4. **Create output envelope**:
   ```python
   from vb_shared.energyplus.envelopes import EnergyPlusOutputEnvelope
   from vb_shared.validations.envelopes import ValidationStatus

   output_envelope = EnergyPlusOutputEnvelope(
       run_id=input_envelope.run_id,
       validator=input_envelope.validator,
       status=ValidationStatus.SUCCESS,
       timing=...,
       messages=[...],
       outputs=EnergyPlusOutputs(...)
   )
   ```

5. **Upload output envelope** to storage:
   ```python
   from validators.core.storage_client import upload_envelope
   from validators.core.envelope_loader import get_output_uri

   output_uri = get_output_uri(input_envelope)
   upload_envelope(output_envelope, output_uri)
   ```

6. **POST callback** (GCP mode only - skipped in self-hosted sync mode):
   ```python
   from validators.core.callback_client import post_callback

   post_callback(
       callback_url=input_envelope.context.callback_url,
       run_id=input_envelope.run_id,
       status=ValidationStatus.SUCCESS,
       result_uri=output_uri,
       skip_callback=input_envelope.context.skip_callback,
   )
   ```

## Dependencies

`validators/core` holds local runtime helpers. Schema models live in `vb_shared` so Django and validators stay in sync.

All validators depend on `vb_shared`:

```toml
# In pyproject.toml
vb-shared @ git+https://github.com/YOUR_ORG/vb_shared.git@main
```

## Building Containers

```bash
# Build a specific validator locally
just build energyplus

# Build all validators
just build-all

# Build and push to Artifact Registry
just build-push energyplus
```

## Deployment

### GCP (Cloud Run Jobs)

```bash
# Deploy to dev stage
just deploy energyplus dev

# Deploy to production
just deploy energyplus prod

# Deploy all validators
just deploy-all prod
```

### Self-Hosted (Docker)

For self-hosted deployments, containers are pulled by Django's Docker runner:

```bash
# Build locally
just build energyplus

# The image will be available as:
# validibot-validator-energyplus:latest
```

Configure Django to use the Docker runner:
```python
VALIDATOR_RUNNER = "docker"
VALIDATOR_RUNNER_OPTIONS = {
    "memory_limit": "4g",
    "cpu_limit": "2.0",
    "timeout_seconds": 3600,
}
```

## Testing

```bash
# Run all tests
just test

# Run tests for a specific validator
just test-validator energyplus

# Run with pytest options
just test -k "test_runner"
```

## Adding a New Validator

1. Copy `validators/energyplus/` as a template
2. Create `__metadata__.py` with validator information
3. Update `Dockerfile` with domain-specific dependencies
4. Implement `runner.py` with validation logic
5. Create typed envelope subclasses in `vb_shared/{domain}/envelopes.py`
6. Update `main.py` to use your typed envelopes
7. Add validator to `justfile` validators list
8. Write tests
9. Deploy as new Cloud Run Job (GCP) or Docker image (self-hosted)
