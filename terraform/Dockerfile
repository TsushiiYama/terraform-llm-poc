FROM hashicorp/terraform:latest

# Install dependencies
RUN apk add --no-cache \
    curl \
    python3 \
    py3-pip \
    bash \
    docker-cli \
    jq

# Set up a virtual environment to avoid external environment issues
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install virtualenv && \
    python3 -m virtualenv /opt/venv

# Activate virtual environment and install packages
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install fastapi uvicorn requests

# Create shared directory for file exchange
RUN mkdir -p /shared

# Copy the API script
COPY ./api/terraform_service.py /app/

# Set working directory
WORKDIR /app

# Default command to start the API service
CMD ["python3", "terraform_service.py"]

# Expose the API port
EXPOSE 8001