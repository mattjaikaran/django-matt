# Django-Matt Development Container
# Python 3.13 with uv pre-installed

FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

# Build arguments
ARG UV_VERSION=0.5.14

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    PATH="/root/.local/bin:/home/vscode/.local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    curl \
    wget \
    git \
    # PostgreSQL client
    postgresql-client \
    libpq-dev \
    # Redis client
    redis-tools \
    # Development utilities
    vim \
    jq \
    htop \
    tree \
    # For mkcert (local SSL)
    libnss3-tools \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

# Install uv for vscode user as well
USER vscode
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install mkcert for local SSL certificates
RUN curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64" \
    && chmod +x mkcert-v*-linux-amd64 \
    && sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert

# Install bun for frontend tooling
RUN curl -fsSL https://bun.sh/install | bash \
    && echo 'export BUN_INSTALL="$HOME/.bun"' >> ~/.bashrc \
    && echo 'export PATH="$BUN_INSTALL/bin:$PATH"' >> ~/.bashrc

# Set working directory
WORKDIR /workspace

# Default command
CMD ["sleep", "infinity"]
