#!/bin/bash

# Docker entrypoint script for Unified MCP Tool Server
# Handles environment setup, health checks, and graceful shutdown

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for dependencies
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local timeout=${4:-30}
    
    log_info "Waiting for $service_name to be ready at $host:$port..."
    
    for i in $(seq 1 $timeout); do
        if timeout 1 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
            log_info "$service_name is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    log_error "$service_name is not available after ${timeout}s"
    return 1
}

# Function to validate environment variables
validate_environment() {
    log_info "Validating environment configuration..."
    
    # Required variables
    required_vars=(
        "MCP_SERVER_NAME"
        "MCP_SERVER_VERSION"
        "MCP_PROTOCOL_VERSION"
        "NEO4J_URI"
        "NEO4J_USER"
        "NEO4J_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    # Validate Neo4j URI format
    if [[ ! "$NEO4J_URI" =~ ^(bolt|neo4j)://.*:[0-9]+$ ]]; then
        log_error "Invalid NEO4J_URI format: $NEO4J_URI"
        exit 1
    fi
    
    # Validate port numbers
    if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
        log_error "Invalid PORT: $PORT"
        exit 1
    fi
    
    if ! [[ "$METRICS_PORT" =~ ^[0-9]+$ ]] || [ "$METRICS_PORT" -lt 1 ] || [ "$METRICS_PORT" -gt 65535 ]; then
        log_error "Invalid METRICS_PORT: $METRICS_PORT"
        exit 1
    fi
    
    log_info "Environment validation passed"
}

# Function to setup directories and permissions
setup_directories() {
    log_info "Setting up directories..."
    
    # Create necessary directories
    mkdir -p /app/logs
    mkdir -p /app/data
    mkdir -p /app/tmp
    
    # Set permissions (if running as root, which shouldn't happen in production)
    if [ "$(id -u)" -eq 0 ]; then
        log_warn "Running as root - this should not happen in production"
        chown -R mcpuser:mcpuser /app/logs /app/data /app/tmp
    fi
    
    log_info "Directory setup complete"
}

# Function to wait for dependencies
wait_for_dependencies() {
    log_info "Checking dependencies..."
    
    # Extract host and port from Neo4j URI
    if [[ "$NEO4J_URI" =~ ^(bolt|neo4j)://([^:]+):([0-9]+)$ ]]; then
        neo4j_host="${BASH_REMATCH[2]}"
        neo4j_port="${BASH_REMATCH[3]}"
        
        # Wait for Neo4j
        wait_for_service "$neo4j_host" "$neo4j_port" "Neo4j" 60
    else
        log_warn "Could not parse Neo4j host/port from URI: $NEO4J_URI"
    fi
    
    log_info "Dependency checks complete"
}

# Function to perform pre-flight checks
preflight_checks() {
    log_info "Performing pre-flight checks..."
    
    # Check Python environment
    python --version
    pip list | grep -E "(mcp|neo4j|structlog|prometheus_client)" || true
    
    # Check disk space
    df -h /app
    
    # Check memory
    free -h
    
    log_info "Pre-flight checks complete"
}

# Function to handle graceful shutdown
graceful_shutdown() {
    log_info "Received shutdown signal, performing graceful shutdown..."
    
    # Send SIGTERM to the main process
    if [ ! -z "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        
        # Wait for graceful shutdown
        for i in $(seq 1 30); do
            if ! kill -0 "$MAIN_PID" 2>/dev/null; then
                log_info "Process shut down gracefully"
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if kill -0 "$MAIN_PID" 2>/dev/null; then
            log_warn "Force killing process"
            kill -KILL "$MAIN_PID" 2>/dev/null || true
        fi
    fi
    
    log_info "Graceful shutdown complete"
    exit 0
}

# Function to start health check background process
start_health_monitor() {
    if [ "$HEALTH_CHECK_ENABLED" = "true" ]; then
        log_info "Starting health monitor..."
        
        while true; do
            sleep 30
            if ! curl -f -s "http://localhost:$PORT/health" > /dev/null; then
                log_error "Health check failed"
                # In a real scenario, you might want to restart the service
                # or send alerts
            fi
        done &
        
        HEALTH_MONITOR_PID=$!
        log_info "Health monitor started (PID: $HEALTH_MONITOR_PID)"
    fi
}

# Main execution function
main() {
    log_info "Starting Unified MCP Tool Server..."
    log_info "Version: $MCP_SERVER_VERSION"
    log_info "Protocol: $MCP_PROTOCOL_VERSION"
    log_info "Transport: $TRANSPORT_TYPE"
    log_info "Host: $HOST:$PORT"
    
    # Setup signal handlers for graceful shutdown
    trap graceful_shutdown SIGTERM SIGINT
    
    # Perform initialization steps
    validate_environment
    setup_directories
    wait_for_dependencies
    preflight_checks
    
    # Start health monitor if enabled
    start_health_monitor
    
    # Log the command being executed
    log_info "Executing command: $@"
    
    # Execute the main command
    exec "$@" &
    MAIN_PID=$!
    
    log_info "Main process started (PID: $MAIN_PID)"
    
    # Wait for the main process
    wait $MAIN_PID
    EXIT_CODE=$?
    
    log_info "Main process exited with code: $EXIT_CODE"
    
    # Cleanup
    if [ ! -z "$HEALTH_MONITOR_PID" ]; then
        kill $HEALTH_MONITOR_PID 2>/dev/null || true
    fi
    
    exit $EXIT_CODE
}

# Handle help command
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Unified MCP Tool Server Docker Entrypoint"
    echo ""
    echo "Environment Variables:"
    echo "  MCP_SERVER_NAME       - Server name (default: unified-tool-server)"
    echo "  MCP_SERVER_VERSION    - Server version (default: 2.0.0)"
    echo "  MCP_PROTOCOL_VERSION  - MCP protocol version (default: 2025-06-18)"
    echo "  TRANSPORT_TYPE        - Transport type (default: streamable-http)"
    echo "  HOST                  - Bind host (default: 0.0.0.0)"
    echo "  PORT                  - Bind port (default: 8000)"
    echo "  METRICS_PORT          - Metrics port (default: 9090)"
    echo "  NEO4J_URI            - Neo4j connection URI"
    echo "  NEO4J_USER           - Neo4j username"
    echo "  NEO4J_PASSWORD       - Neo4j password"
    echo "  LOG_LEVEL            - Log level (default: INFO)"
    echo "  HEALTH_CHECK_ENABLED - Enable health monitoring (default: true)"
    echo "  METRICS_ENABLED      - Enable metrics collection (default: true)"
    echo ""
    echo "Commands:"
    echo "  Default: Start the MCP server"
    echo "  --help:  Show this help message"
    exit 0
fi

# Execute main function
main "$@"