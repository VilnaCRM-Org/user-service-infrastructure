# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set build-time variables for UID and GID with defaults
ARG UID=1000
ARG GID=1000
ARG USERNAME=appuser

# Install system dependencies as root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create home directory and set ownership
RUN mkdir -p /home/${USERNAME} && chown ${UID}:${GID} /home/${USERNAME}

# Set environment variables
ENV PATH="/home/${USERNAME}/.local/bin:/home/${USERNAME}/.pulumi/bin:${PATH}"
ENV HOME=/home/${USERNAME}
WORKDIR /home/${USERNAME}

# Switch to the user with specified UID and GID
USER ${UID}:${GID}

# Install Pulumi
RUN curl -fsSL https://get.pulumi.com | bash

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ~/.local/bin/poetry config virtualenvs.in-project true

# Install AWS CLI
RUN mkdir awscliv2 && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2/awscliv2.zip" && \
    unzip awscliv2/awscliv2.zip -d awscliv2 && \
    awscliv2/aws/install --install-dir /home/${USERNAME}/.aws-cli --bin-dir /home/${USERNAME}/.local/bin && \
    rm -rf awscliv2

# Verify installations (optional)
RUN pulumi version && poetry --version && aws --version

# Set the default command
CMD ["bash"]
