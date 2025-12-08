# =============================================================================
# Validibot Validators Justfile
# =============================================================================
#
# Build and deploy validator containers for Cloud Run Jobs.
#
# Usage:
#   just                    # List all available commands
#   just build energyplus   # Build a specific validator
#   just build-all          # Build all validators
#   just deploy energyplus  # Deploy to Cloud Run Jobs
#
# =============================================================================

set shell := ["bash", "-cu"]

# =============================================================================
# Configuration
# =============================================================================

# GCP defaults (override with: just --set gcp_project "my-project" build energyplus)
gcp_project := "project-a509c806-3e21-4fbc-b19"
gcp_region := "australia-southeast1"

# Artifact Registry path
ar_host := gcp_region + "-docker.pkg.dev"
ar_repo := ar_host + "/" + gcp_project + "/validibot"

# Git SHA for tagging
git_sha := `git rev-parse --short HEAD 2>/dev/null || echo "dev"`

# Available validators
validators := "energyplus fmi"

# =============================================================================
# Default - List Commands
# =============================================================================

@default:
    just --list

# =============================================================================
# Development
# =============================================================================

# Run all tests
test *args:
    uv run pytest {{args}}

# Run tests for a specific validator
test-validator validator:
    uv run pytest validators/{{validator}}/tests

# Lint all code
lint:
    uv run ruff check .

# Lint and fix
lint-fix:
    uv run ruff check . --fix

# Format code
format:
    uv run ruff format .

# Type check
typecheck:
    uv run mypy .

# Run all checks (lint + test)
check: lint test

# =============================================================================
# Docker Build
# =============================================================================

# Build a validator container locally
# Build context is the repo root (vb_validators/), not the validator subdirectory
# Builds for linux/amd64 since Cloud Run requires that architecture
build validator:
    @echo "Building {{validator}} container..."
    docker build \
        --platform linux/amd64 \
        -f validators/{{validator}}/Dockerfile \
        -t validibot-validator-{{validator}}:latest \
        -t validibot-validator-{{validator}}:{{git_sha}} \
        .
    @echo "✓ Built validibot-validator-{{validator}}:{{git_sha}}"

# Build all validator containers
build-all:
    #!/usr/bin/env bash
    set -euo pipefail
    for v in {{validators}}; do
        just build "$v"
    done
    echo "✓ All validators built"

# =============================================================================
# Docker Push (to Artifact Registry)
# =============================================================================

# Tag and push a validator to Artifact Registry
push validator:
    @echo "Pushing {{validator}} to Artifact Registry..."
    docker tag validibot-validator-{{validator}}:latest {{ar_repo}}/validibot-validator-{{validator}}:latest
    docker tag validibot-validator-{{validator}}:{{git_sha}} {{ar_repo}}/validibot-validator-{{validator}}:{{git_sha}}
    docker push {{ar_repo}}/validibot-validator-{{validator}}:latest
    docker push {{ar_repo}}/validibot-validator-{{validator}}:{{git_sha}}
    @echo "✓ Pushed {{ar_repo}}/validibot-validator-{{validator}}:{{git_sha}}"

# Push all validators
push-all:
    #!/usr/bin/env bash
    set -euo pipefail
    for v in {{validators}}; do
        just push "$v"
    done
    echo "✓ All validators pushed"

# =============================================================================
# Cloud Run Jobs Deployment
# =============================================================================

# Deploy a validator as a Cloud Run Job (creates or updates)
deploy validator:
    @echo "Deploying {{validator}} to Cloud Run Jobs..."
    just build {{validator}}
    just push {{validator}}
    @echo "Creating/updating Cloud Run Job..."
    gcloud run jobs deploy validibot-validator-{{validator}} \
        --image {{ar_repo}}/validibot-validator-{{validator}}:{{git_sha}} \
        --region {{gcp_region}} \
        --project {{gcp_project}} \
        --memory 4Gi \
        --cpu 2 \
        --max-retries 0 \
        --task-timeout 3600 \
        --set-env-vars "PYTHONUNBUFFERED=1"
    @echo "✓ Deployed validibot-validator-{{validator}}"

# Deploy all validators
deploy-all:
    #!/usr/bin/env bash
    set -euo pipefail
    for v in {{validators}}; do
        just deploy "$v"
    done
    echo "✓ All validators deployed"

# =============================================================================
# Cloud Run Jobs Management
# =============================================================================

# List all validator jobs
list-jobs:
    gcloud run jobs list \
        --region {{gcp_region}} \
        --project {{gcp_project}} \
        --filter "name~validibot-validator"

# Show job details
describe-job validator:
    gcloud run jobs describe validibot-validator-{{validator}} \
        --region {{gcp_region}} \
        --project {{gcp_project}}

# View recent job logs
logs validator lines="100":
    gcloud logging read \
        'resource.type="cloud_run_job" AND resource.labels.job_name="validibot-validator-{{validator}}"' \
        --project {{gcp_project}} \
        --limit {{lines}} \
        --format "table(timestamp,textPayload)"

# Delete a validator job
delete-job validator:
    @echo "Deleting Cloud Run Job validibot-validator-{{validator}}..."
    gcloud run jobs delete validibot-validator-{{validator}} \
        --region {{gcp_region}} \
        --project {{gcp_project}} \
        --quiet
    @echo "✓ Deleted validibot-validator-{{validator}}"

# =============================================================================
# Local Development Helpers
# =============================================================================

# Run a validator container locally (for testing)
run-local validator input_uri:
    docker run --rm \
        -e INPUT_URI={{input_uri}} \
        -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/adc.json \
        -v "$HOME/.config/gcloud/application_default_credentials.json:/tmp/keys/adc.json:ro" \
        validibot-validator-{{validator}}:latest

# Shell into a validator container (for debugging)
shell validator:
    docker run --rm -it \
        --entrypoint /bin/bash \
        validibot-validator-{{validator}}:latest

# =============================================================================
# CI/CD Helpers
# =============================================================================

# Build, test, and deploy (for CI)
ci-deploy validator:
    just lint
    just test-validator {{validator}}
    just deploy {{validator}}

# Verify all validators are deployable (dry run)
verify-all:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Verifying all validators..."
    just lint
    just test
    for v in {{validators}}; do
        just build "$v"
    done
    echo "✓ All validators verified"
