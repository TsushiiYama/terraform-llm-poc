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

# Set working directory
WORKDIR /app

# Default command to start the API service (full path to the Python in virtual env)
CMD ["/opt/venv/bin/python3", "/app/terraform_service.py"]

# Expose the API port
EXPOSE 8001
