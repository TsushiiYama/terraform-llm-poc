FROM hashicorp/terraform:latest

# Install dependencies
RUN apk add --no-cache \
    curl \
    python3 \
    py3-pip \
    bash \
    docker-cli \
    jq

# Install Python packages
RUN pip3 install fastapi uvicorn requests

# Create shared directory for file exchange
RUN mkdir -p /shared

# Copy the API script (we'll create this later)
COPY ./api/terraform_service.py /app/

# Set working directory
WORKDIR /app

# Default command to start the API service
CMD ["python3", "terraform_service.py"]

# Expose the API port
EXPOSE 8001