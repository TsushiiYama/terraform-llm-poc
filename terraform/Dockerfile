FROM hashicorp/terraform:latest

# Install dependencies
RUN apk add --no-cache \
    curl \
    python3 \
    py3-pip \
    bash \
    docker-cli \
    jq \
    python3-dev \
    py3-virtualenv

# Create a virtual environment directly with venv
RUN python3 -m venv /opt/venv

# Activate virtual environment and install packages
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install fastapi uvicorn requests

# Create shared directory for file exchange
RUN mkdir -p /shared

# Copy the API script
COPY ./api/terraform_service.py /app/

# Create an entrypoint script
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'cd /app' >> /entrypoint.sh && \
    echo '/opt/venv/bin/python3 terraform_service.py' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Set working directory
WORKDIR /app

# Use ENTRYPOINT to override the default Terraform entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (empty because we're using ENTRYPOINT)
CMD []

# Expose the API port
EXPOSE 8001