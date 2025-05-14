FROM ollama/ollama:latest

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install fastapi uvicorn requests

# Copy the API script (we'll create this later)
COPY ./api/ollama_service.py /app/

# Create a directory for shared files
RUN mkdir -p /shared

# Set working directory
WORKDIR /app

# Default command to start the API service
CMD ["python3", "ollama_service.py"]

# Expose the API port
EXPOSE 8000