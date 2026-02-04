<div align="center">

# Validibot Advanced Validators

**Advanced validator containers for the Validibot data validation platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

[Available Validators](#available-validators) •
[Quick Start](#quick-start) •
[Creating Custom Validators](#creating-a-custom-validator) •
[Deployment](#deployment)

</div>

---

> [!NOTE]
> This repository is part of the [Validibot](https://github.com/danielmcquillen/validibot) open-source data validation platform. These containers provide advanced validation capabilities that run in isolated Docker environments.

---

## Part of the Validibot Project

This repository is one component of the Validibot open-source data validation platform:

| Repository                                                                                      | Description                                       |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| **[validibot](https://github.com/danielmcquillen/validibot)**                                   | Core platform — web UI, REST API, workflow engine |
| **[validibot-cli](https://github.com/danielmcquillen/validibot-cli)**                           | Command-line interface                            |
| **[validibot-validators](https://github.com/danielmcquillen/validibot-validators)** (this repo) | Advanced validator containers                     |
| **[validibot-shared](https://github.com/danielmcquillen/validibot-shared)**                     | Shared Pydantic models for data interchange       |

## What are Validibot Validators?

Validibot Validators are Docker containers that perform specialized, resource-intensive validations. Unlike Validibot's built-in validators (JSON Schema, XML Schema, etc.) that run directly in the Django process, advanced validators:

- **Run in isolation** — Each validation runs in its own container with resource limits
- **Have complex dependencies** — EnergyPlus, FMPy, and other domain-specific tools
- **Are secure by default** — Network isolation, memory limits, and automatic cleanup
- **Scale independently** — Can run on separate infrastructure from the core platform

The core Validibot platform triggers these containers, passes input via the standardized envelope format (defined in [validibot-shared](https://github.com/danielmcquillen/validibot-shared)), and processes the results when complete.

## Available Validators

| Validator      | Description                                    | Use Cases                                                        |
| -------------- | ---------------------------------------------- | ---------------------------------------------------------------- |
| **EnergyPlus** | Validates and simulates building energy models | IDF/epJSON schema validation, simulation runs, energy metrics    |
| **FMI**        | Validates and probes Functional Mock-up Units  | FMU structure validation, variable discovery, simulation testing |

## How It Works

Validators receive work via a standardized "envelope" containing:

- **Input files** — URIs to files being validated (GCS or local filesystem)
- **Configuration** — Validator-specific settings (e.g., simulation timestep)
- **Context** — Callback URL, execution bundle location, timeout settings

After running validation, the container writes an output envelope with:

- **Status** — success, failure, or error
- **Messages** — Validation findings (errors, warnings, info)
- **Metrics** — Numeric results (e.g., EUI for building models)
- **Artifacts** — Generated files (reports, logs, etc.)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Validibot Core Platform                       │
│                                                                  │
│  1. Creates input envelope                                       │
│  2. Uploads to storage (GCS or local)                           │
│  3. Triggers validator container                                 │
│  4. Waits for completion (sync or callback)                      │
│  5. Processes output envelope                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Validator Container                           │
│                                                                  │
│  1. Loads input envelope from storage                            │
│  2. Downloads input files                                        │
│  3. Runs validation/simulation                                   │
│  4. Creates output envelope with results                         │
│  5. Uploads output envelope                                      │
│  6. Sends callback (if async mode)                               │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker (or Podman)
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- [just](https://github.com/casey/just) command runner

### Building Containers

```bash
# Clone the repository
git clone https://github.com/danielmcquillen/validibot-validators.git
cd validibot-validators

# Build a specific validator
just build energyplus

# Build all validators
just build-all

# List available commands
just --list
```

### Running Tests

```bash
# Install dev dependencies
uv sync --extra dev

# Run all tests
just test

# Run tests for a specific validator
just test-validator energyplus
```

## Deployment Modes

Validators support two deployment modes:

### Self-Hosted (Docker)

For self-hosted Validibot deployments, validators run as local Docker containers:

```bash
# Build the container
just build energyplus

# The image will be available as:
# validibot-validator-energyplus:latest
```

The core platform's Celery worker manages container lifecycle:

```
Django Worker → Docker API → Validator Container → Local Storage
     ↑                                                    │
     └────────────── Reads output.json ───────────────────┘
```

**Characteristics:**

- Synchronous execution (worker blocks until container exits)
- Local filesystem storage (`file://` URIs)
- No callback needed — worker reads results directly

### GCP Cloud Run Jobs

For cloud deployments, validators run as Cloud Run Jobs:

```bash
# Build and push to Artifact Registry
just build-push energyplus

# Deploy to Cloud Run Jobs
just deploy energyplus prod
```

```
Cloud Run Service → Cloud Tasks → Cloud Run Job → GCS Storage
        ↑                                              │
        └───────────── Callback POST ──────────────────┘
```

**Characteristics:**

- Asynchronous execution (triggered via Cloud Tasks)
- GCS storage (`gs://` URIs)
- HTTP callback when complete

## Configuration

### Environment Variables

Validators receive configuration via environment variables:

| Variable               | Required | Description                                           |
| ---------------------- | -------- | ----------------------------------------------------- |
| `VALIDIBOT_INPUT_URI`  | Yes      | Storage URI to input envelope                         |
| `VALIDIBOT_OUTPUT_URI` | No       | Storage URI for output (defaults to sibling of input) |
| `VALIDIBOT_RUN_ID`     | No       | Validation run ID (for logging)                       |

### Storage URIs

Validators support two storage backends:

```
# Google Cloud Storage (GCP deployments)
gs://my-bucket/runs/org-123/run-456/input.json

# Local filesystem (self-hosted deployments)
file:///app/storage/private/runs/org-123/run-456/input.json
```

### Django Configuration

Configure the core platform to use Docker validators:

```python
# settings/local.py or settings/production.py
VALIDATOR_RUNNER = "docker"
VALIDATOR_RUNNER_OPTIONS = {
    "memory_limit": "4g",
    "cpu_limit": "2.0",
    "timeout_seconds": 3600,
    "network_mode": "none",  # Network isolation
}
```

## Directory Structure

```
validibot-validators/
├── justfile                   # Build/deploy commands
├── pyproject.toml            # Python project config
└── validators/
    ├── core/                 # Shared utilities
    │   ├── storage_client.py     # Storage I/O (gs:// and file://)
    │   ├── callback_client.py    # HTTP callback utilities
    │   └── envelope_loader.py    # Envelope serialization
    │
    ├── energyplus/           # EnergyPlus validator
    │   ├── Dockerfile
    │   ├── __metadata__.py   # Validator metadata
    │   ├── main.py           # Container entrypoint
    │   ├── runner.py         # Simulation logic
    │   └── tests/
    │
    └── fmi/                  # FMI/FMU validator
        ├── Dockerfile
        ├── __metadata__.py
        ├── main.py
        ├── runner.py
        └── tests/
```

## Creating a Custom Validator

You can create custom validators for domain-specific validation needs.

### 1. Create Validator Directory

```bash
cp -r validators/energyplus validators/myvalidator
```

### 2. Define Metadata

Edit `validators/myvalidator/__metadata__.py`:

```python
METADATA = {
    "validator_type": "MYVALIDATOR",
    "validator_name": "My Custom Validator",
    "image_name": "validibot-validator-myvalidator",
    "supported_input_types": ["application/json"],
    "resource_requirements": {
        "memory": "2g",
        "cpu": "1.0",
        "timeout_seconds": 600,
    },
}

def get_metadata():
    return METADATA
```

### 3. Create Typed Envelopes

In [validibot-shared](https://github.com/danielmcquillen/validibot-shared), define your typed envelopes:

```python
# validibot_shared/myvalidator/envelopes.py
from pydantic import BaseModel
from validibot_shared.validations.envelopes import (
    ValidationInputEnvelope,
    ValidationOutputEnvelope,
)

class MyValidatorInputs(BaseModel):
    strict_mode: bool = False
    max_errors: int = 100

class MyValidatorOutputs(BaseModel):
    items_checked: int
    items_passed: int

class MyValidatorInputEnvelope(ValidationInputEnvelope):
    inputs: MyValidatorInputs

class MyValidatorOutputEnvelope(ValidationOutputEnvelope):
    outputs: MyValidatorOutputs | None = None
```

### 4. Implement Runner

Edit `validators/myvalidator/runner.py`:

```python
from validibot_shared.myvalidator.envelopes import (
    MyValidatorInputEnvelope,
    MyValidatorOutputEnvelope,
    MyValidatorOutputs,
)
from validibot_shared.validations.envelopes import ValidationMessage, ValidationStatus

def run_validation(envelope: MyValidatorInputEnvelope) -> MyValidatorOutputEnvelope:
    messages = []
    items_checked = 0
    items_passed = 0

    # Your validation logic here
    for input_file in envelope.input_files:
        items_checked += 1
        # ... validate file ...
        if valid:
            items_passed += 1
        else:
            messages.append(ValidationMessage(
                severity="error",
                code="MY001",
                text=f"Validation failed for {input_file.name}",
            ))

    status = ValidationStatus.SUCCESS if not messages else ValidationStatus.FAILURE

    return MyValidatorOutputEnvelope(
        run_id=envelope.run_id,
        validator=envelope.validator,
        status=status,
        messages=messages,
        outputs=MyValidatorOutputs(
            items_checked=items_checked,
            items_passed=items_passed,
        ),
    )
```

### 5. Update Dockerfile

Edit `validators/myvalidator/Dockerfile` to install your dependencies:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install your domain-specific tools
RUN apt-get update && apt-get install -y \
    your-tool \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "-m", "validators.myvalidator.main"]
```

### 6. Build and Test

```bash
# Build your validator
just build myvalidator

# Run tests
just test-validator myvalidator
```

## Validator Contract

Every validator container must follow this contract:

1. **Read input location** from `VALIDIBOT_INPUT_URI` environment variable
2. **Load input envelope** from storage using typed Pydantic model
3. **Download input files** from URIs in `input_envelope.input_files`
4. **Run validation** using configuration from `input_envelope.inputs`
5. **Create output envelope** with status, messages, metrics, artifacts
6. **Upload output envelope** to storage
7. **POST callback** (GCP mode only) or exit (self-hosted mode)

The `validators.core` module provides helpers for steps 2, 5, 6, and 7.

### How It Fits Together

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              End Users                                       │
│                    (Web UI, CLI, REST API clients)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         validibot (core platform)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Web UI  │  REST API  │  Workflow Engine  │  Built-in Validators   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│            Triggers Docker containers for advanced validations              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ validibot-cli   │    │ validibot-validators│    │ validibot-shared    │
│                 │    │   (this repo)       │    │                     │
│ Terminal access │    │                     │    │ Pydantic models     │
│ to API          │    │ EnergyPlus, FMI     │    │ (shared contract)   │
│                 │    │ containers          │    │                     │
└─────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Development

```bash
# Clone the repository
git clone https://github.com/danielmcquillen/validibot-validators.git
cd validibot-validators

# Install dependencies
uv sync --extra dev

# Run linter
uv run ruff check .

# Run type checker
uv run mypy validators/

# Run tests
uv run pytest
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

[Validibot Platform](https://github.com/danielmcquillen/validibot) •
[Documentation](https://docs.validibot.com) •
[Report Issues](https://github.com/danielmcquillen/validibot-validators/issues)

</div>
