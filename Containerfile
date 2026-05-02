FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install system dependencies including ODBC drivers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    unixodbc-dev \
    odbcinst \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install API dependencies (fastapi, uvicorn) for the API server
RUN pip install --no-cache-dir fastapi uvicorn

# Expose port
EXPOSE 8084

# Set environment variables (can be overridden at runtime)
ENV PRODUCTION_MODE=true

# Entry point
ENTRYPOINT ["python", "src/vanna_grok.py"]
