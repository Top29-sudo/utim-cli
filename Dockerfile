# UTIM Server Dockerfile
# Multi-stage build for optimized image size and proper dependency isolation

FROM python:3.11-slim AS base

# Install system dependencies including Docker client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    lsb-release \
    docker.io \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI using official Docker repository for latest version
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && rm -rf /var/lib/apt/lists/*

# Pre-pull sandbox image to avoid first-run delays
RUN docker pull ubuntu:22.04 || true

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set up work directory
WORKDIR /app

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Create non-root user for security
RUN useradd -m -u 1000 utim && chown -R utim:utim /app
USER utim

# Default command runs the server (restructures flat context to package context dynamically if needed)
CMD ["sh", "-c", "if [ ! -d utim_cli ]; then mkdir -p /tmp/utim_flat && mv * /tmp/utim_flat/ 2>/dev/null || true && mkdir -p utim_cli/server && touch utim_cli/__init__.py && touch utim_cli/server/__init__.py && mv /tmp/utim_flat/* utim_cli/server/ 2>/dev/null || true; fi; python utim_cli/server/server.py --host 0.0.0.0 --port 8000"]