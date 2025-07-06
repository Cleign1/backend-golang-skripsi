FROM python:3.11-slim

# Set working directory
WORKDIR /app
# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# Copy requirements first for better caching
COPY requirements.txt .

RUN uv venv

RUN /bin/bash -c "source .venv/bin/activate"

# Install Python dependencies
RUN uv pip install -r requirements.txt

# Copy application code
COPY . .

# Create directory for prediction results
RUN mkdir -p prediction_results

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["uv", "run", "python", "main.py"]