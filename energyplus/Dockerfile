# Multi-stage build for EnergyPlus validator container
#
# Build context must be vb_validators_dev/ (not energyplus/)
# Build with: docker build -f energyplus/Dockerfile -t ... .

# =============================================================================
# Stage 1: Build EnergyPlus
# =============================================================================
FROM ubuntu:22.04 AS energyplus-builder

# Install EnergyPlus build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Download and install EnergyPlus 24.2.0
# Update this URL for different EnergyPlus versions
RUN wget -q https://github.com/NREL/EnergyPlus/releases/download/v24.2.0/EnergyPlus-24.2.0-9f1b36b00b-Linux-Ubuntu22.04-x86_64.tar.gz \
    && tar -xzf EnergyPlus-24.2.0-9f1b36b00b-Linux-Ubuntu22.04-x86_64.tar.gz \
    && mv EnergyPlus-24.2.0-9f1b36b00b-Linux-Ubuntu22.04-x86_64 /opt/energyplus \
    && rm EnergyPlus-24.2.0-9f1b36b00b-Linux-Ubuntu22.04-x86_64.tar.gz

# =============================================================================
# Stage 2: Runtime container
# =============================================================================
FROM python:3.13-slim

# Install runtime dependencies (git needed for pip install from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy EnergyPlus from builder stage
COPY --from=energyplus-builder /opt/energyplus /opt/energyplus

# Add EnergyPlus to PATH
ENV PATH="/opt/energyplus:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
# Build context is vb_validators_dev/
COPY energyplus/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy core utilities (shared by all validators)
COPY core /app/validators/core

# Copy validator code
COPY energyplus /app/validators/energyplus

# Create working directory for EnergyPlus runs
RUN mkdir -p /tmp/energyplus_run

# Set entrypoint
WORKDIR /app/validators/energyplus
CMD ["python", "main.py"]
