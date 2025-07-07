# Multi-stage Dockerfile for Unified MCP Tool Server
# Following SDE best practices for production deployment

# ================================
# Build Stage
# ================================
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_VERSION=2.0.0
ARG BUILD_DATE
ARG VCS_REF

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /build

# Copy dependency files
COPY requirements.txt .
COPY pyproject.toml .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# ================================
# Production Stage
# ================================
FROM python:3.11-slim as production

# Set metadata labels
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="unified-mcp-tool-server" \
      org.label-schema.description="Unified MCP Tool Server with StreamableHTTP transport" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vcs-url="https://github.com/your-org/unified-mcp-tool-graph" \
      org.label-schema.vendor="Unified MCP Tool Graph" \
      org.label-schema.version=$BUILD_VERSION \
      org.label-schema.schema-version="1.0"

# Create non-root user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set work directory
WORKDIR /app

# Copy application code
COPY --chown=mcpuser:mcpuser . .

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data && \
    chown -R mcpuser:mcpuser /app

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_SERVER_NAME=unified-tool-server \
    MCP_SERVER_VERSION=$BUILD_VERSION \
    MCP_PROTOCOL_VERSION=2025-06-18 \
    TRANSPORT_TYPE=streamable-http \
    HOST=0.0.0.0 \
    PORT=8000 \
    METRICS_PORT=9090 \
    LOG_LEVEL=INFO \
    HEALTH_CHECK_ENABLED=true \
    METRICS_ENABLED=true

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER mcpuser

# Add entrypoint script
COPY --chown=mcpuser:mcpuser docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command
CMD ["python", "-m", "unified_mcp_server"]