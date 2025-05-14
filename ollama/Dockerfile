FROM ollama/ollama:latest

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment to avoid external environment issues
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install virtualenv && \
    python3 -m virtualenv /opt/venv

# Activate virtual environment and install packages
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install fastapi uvicorn requests

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