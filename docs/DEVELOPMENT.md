# Development Guide

This guide helps developers set up and contribute to the Unified MCP Tool Graph project.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 16+ (for Node.js-based MCP servers)
- Git
- Docker (optional, for local services)

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/unified-mcp-tool-graph.git
cd unified-mcp-tool-graph
```

### 2. Install Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync

# Install development dependencies (if any)
uv sync --dev
```

### 3. Configure Environment

```bash
# Copy environment template
cp env.example .env

# Edit .env with your local configuration
# At minimum, configure Neo4j if you want dynamic tool retrieval
```

### 4. Set Up Local Services (Optional)

#### Using Docker Compose

```bash
# Start Neo4j, PostgreSQL, Redis
docker-compose up -d neo4j postgres redis

# Wait for services to be ready
docker-compose ps
```

#### Manual Setup

- **Neo4j**: Follow [Neo4j installation guide](https://neo4j.com/docs/operations-manual/current/installation/)
- **PostgreSQL**: Install and create database
- **Redis**: Install and start Redis server

### 5. Initialize Database

```bash
# Run database initialization script
psql -U postgres -d mcp_gateway -f scripts/init_db.sql

# Run ingestion pipeline (if Neo4j is set up)
uv run python Ingestion_pipeline/Ingestion_Neo4j.py
```

### 6. Start Development Server

```bash
# Start the gateway
uv run python start_unified_gateway.py

# Or use uvicorn directly for hot reload
uv run uvicorn gateway.unified_gateway:app --reload --port 8000
```

## Project Structure

See [docs/STRUCTURE.md](STRUCTURE.md) for detailed project organization.

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

- Follow PEP 8 style guidelines
- Use type hints
- Add docstrings
- Write tests for new features

### 3. Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_gateway.py

# Run with verbose output
uv run pytest -v
```

### 4. Lint and Format

```bash
# Check code style
uv run ruff check .

# Format code (if ruff supports it)
uv run ruff format .

# Type checking
uv run mypy . --ignore-missing-imports
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: Add new feature description"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Standards

### Python Style

- **Formatter**: Use `ruff` or `black`
- **Line Length**: 100 characters
- **Type Hints**: Use type hints for all functions
- **Docstrings**: Google or NumPy style

### Example

```python
def discover_tools(
    query: str,
    limit: int = 5,
    include_config: bool = True
) -> Dict[str, Any]:
    """
    Discover tools based on a natural language query.
    
    Args:
        query: Natural language description of desired tools
        limit: Maximum number of tools to return
        include_config: Whether to include MCP server configs
        
    Returns:
        Dictionary containing discovered tools and metadata
        
    Raises:
        ValueError: If query is empty
    """
    if not query:
        raise ValueError("Query cannot be empty")
    # Implementation...
```

### Testing Standards

- **Coverage**: Aim for >80% code coverage
- **Unit Tests**: Test individual functions/classes
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test full workflows

### Example Test

```python
import pytest
from gateway.unified_gateway import discover_tools

def test_discover_tools_success():
    """Test successful tool discovery."""
    result = discover_tools("schedule post", limit=5)
    assert "tools" in result
    assert len(result["tools"]) <= 5

def test_discover_tools_empty_query():
    """Test that empty query raises error."""
    with pytest.raises(ValueError):
        discover_tools("")
```

## Debugging

### Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG
ENABLE_REQUEST_LOGGING=true
```

### Use Debugger

```python
import pdb; pdb.set_trace()  # Python debugger
# or
import ipdb; ipdb.set_trace()  # IPython debugger (if installed)
```

### Check Logs

```bash
# Docker logs
docker-compose logs -f gateway

# Application logs
tail -f logs/gateway.log
```

## Common Tasks

### Adding a New MCP Server

1. Add server config to `config/mcp_proxy_servers.json.example`
2. Update documentation if needed
3. Test server connection
4. Add to ingestion pipeline if needed

### Adding a New API Endpoint

1. Add route to `gateway/unified_gateway.py`
2. Add request/response models
3. Write tests
4. Update API documentation

### Modifying Database Schema

1. Create migration script in `scripts/migrations/`
2. Update `scripts/init_db.sql`
3. Test migration
4. Document changes

## Performance Testing

```bash
# Use Apache Bench or similar
ab -n 1000 -c 10 http://localhost:8000/health

# Or use Python script
uv run python scripts/benchmark.py
```

## Documentation

### Updating Documentation

- **API Docs**: Update `docs/API.md`
- **Architecture**: Update `ARCHITECTURE.md`
- **Deployment**: Update `docs/DEPLOYMENT.md`
- **Code Comments**: Keep inline comments up to date

### Building Documentation

```bash
# If using Sphinx or similar
uv run sphinx-build docs/ docs/_build/
```

## Troubleshooting

### Import Errors

```bash
# Ensure you're using uv run
uv run python script.py

# Or activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill process or change port in .env
```

### Database Connection Issues

```bash
# Check if services are running
docker-compose ps

# Check connection
psql -U postgres -d mcp_gateway -c "SELECT 1;"
```

## Getting Help

- **Documentation**: Check `docs/` directory
- **Issues**: Search existing GitHub issues
- **Discussions**: Use GitHub Discussions
- **Questions**: Open a GitHub issue with question label

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [uv Documentation](https://docs.astral.sh/uv/)

