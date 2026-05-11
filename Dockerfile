FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the MCP server over SSE using Uvicorn
# Uvicorn listens on $PORT, default 8080 for Cloud Run
CMD ["sh", "-c", "uvicorn mcp_server:starlette_app --host 0.0.0.0 --port ${PORT:-8080}"]
