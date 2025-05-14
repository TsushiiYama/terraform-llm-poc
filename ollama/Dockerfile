FROM ollama/ollama:latest

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment directly with venv
RUN python3 -m venv /opt/venv

# Activate virtual environment and install packages
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install fastapi uvicorn requests

# Create a directory for shared files
RUN mkdir -p /shared

# Copy the API script
COPY ./api/ollama_service.py /app/

# Set working directory
WORKDIR /app

# Default command to start the API service
CMD ["python3", "ollama_service.py"]

# Expose the API port
EXPOSE 8000