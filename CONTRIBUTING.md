# Contributing to Unified MCP Tool Graph

Thank you for your interest in contributing to Unified MCP Tool Graph! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/unified-mcp-tool-graph.git
   cd unified-mcp-tool-graph
   ```
3. **Set up the development environment**:
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install dependencies
   uv sync
   ```

## 📝 Development Workflow

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following our coding standards:
   - Follow PEP 8 style guidelines
   - Use type hints where appropriate
   - Add docstrings to functions and classes
   - Write clear, descriptive commit messages

3. **Test your changes**:
   ```bash
   # Run the gateway to test
   uv run python start_unified_gateway.py
   
   # Run tests if available
   uv run pytest
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request** on GitHub

## 🎯 Contribution Areas

We welcome contributions in the following areas:

- **New MCP Server Integrations**: Add support for new MCP servers
- **Documentation**: Improve documentation, add examples, fix typos
- **Bug Fixes**: Fix issues and bugs
- **Performance Improvements**: Optimize code and improve performance
- **Testing**: Add tests for existing or new functionality
- **Examples**: Add example agents or use cases

## 📋 Code Standards

### Python Code Style

- Use **Black** for code formatting (or follow PEP 8)
- Maximum line length: 100 characters
- Use type hints for function parameters and return types
- Add docstrings following Google or NumPy style

### Commit Messages

Use clear, descriptive commit messages:

```
feat: Add support for new MCP server
fix: Resolve connection timeout issue
docs: Update getting started guide
refactor: Simplify server manager code
test: Add tests for tool routing
```

### Pull Request Guidelines

- **Keep PRs focused**: One feature or fix per PR
- **Write clear descriptions**: Explain what and why
- **Reference issues**: Link to related issues
- **Update documentation**: If your changes affect usage, update docs
- **Add tests**: Include tests for new functionality

## 🧪 Testing

Before submitting a PR, ensure:

- [ ] Code follows project style guidelines
- [ ] All tests pass (if applicable)
- [ ] New functionality is tested
- [ ] Documentation is updated
- [ ] No linter errors

## 📚 Project Structure

```
unified-mcp-tool-graph/
├── gateway/              # Unified gateway implementation
├── MCP_Server_Manager/   # MCP server management
├── Dynamic_tool_retriever_MCP/  # Dynamic tool retrieval
├── Example_Agents/      # Example agent implementations
├── Ingestion_pipeline/   # Tool ingestion scripts
├── Utils/               # Utility functions
└── experimental/        # Experimental features (use with caution)
```

## 🐛 Reporting Issues

When reporting bugs or requesting features:

1. **Check existing issues** to avoid duplicates
2. **Use clear titles** and descriptions
3. **Include reproduction steps** for bugs
4. **Provide environment details** (OS, Python version, etc.)
5. **Include error messages** and logs if applicable

## ❓ Questions?

- Open an issue for questions or discussions
- Check existing issues and discussions
- Review the documentation in `GETTING_STARTED.md`

## 📜 License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

Thank you for contributing! 🎉

