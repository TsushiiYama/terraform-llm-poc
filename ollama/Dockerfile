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

# Create an entrypoint script
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'cd /app' >> /entrypoint.sh && \
    echo '/opt/venv/bin/python3 ollama_service.py' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Set working directory
WORKDIR /app

# Use ENTRYPOINT to override the default Ollama entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (empty because we're using ENTRYPOINT)
CMD []

# Expose the API port
EXPOSE 8000