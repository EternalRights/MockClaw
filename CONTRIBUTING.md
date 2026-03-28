# Contributing to MockClaw

Thank you for your interest in contributing to MockClaw. This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)

## Code of Conduct

This project and everyone participating in it is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- Docker (optional)

### Local Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/MockClaw.git
cd MockClaw

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r src/requirements.txt
pip install -r requirements-dev.txt  # Dev dependencies
cd web && npm install && cd ..

# Set up pre-commit hooks
pre-commit install
```

## How to Contribute

### Reporting Bugs

Before submitting a bug report:

1. Check existing issues to avoid duplicates
2. Use a clear, descriptive title
3. Include steps to reproduce
4. Describe expected vs actual behavior
5. Include environment details (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are welcome. Please:

1. Use a clear title
2. Provide a detailed description
3. Explain why this would be useful
4. Include examples if applicable

### Code Contributions

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Commit: `git commit -m "feat: description"`
6. Push: `git push origin feature/your-feature`
7. Open a pull request

## Pull Request Process

1. **Branch Naming**: Use descriptive names
   - `feature/add-graphql-support`
   - `fix/docker-connection-issue`
   - `docs/update-api-reference`

2. **Commit Messages**: Follow conventional commits
   - `feat:` - New features
   - `fix:` - Bug fixes
   - `docs:` - Documentation changes
   - `test:` - Test additions/modifications
   - `refactor:` - Code refactoring
   - `chore:` - Maintenance tasks

3. **Pull Request Title**: Clear and descriptive

4. **Description**: Include
   - What changes were made
   - Why they were made
   - How to test them
   - Any breaking changes

5. **Review Requirements**:
   - All tests must pass
   - Code coverage must not decrease
   - Documentation must be updated
   - At least one approval required

## Coding Standards

### Python

- Follow PEP 8 style guide
- Use type hints for all functions
- Maximum line length: 88 characters
- Use docstrings (Google style)

```python
def parse_har(file_path: str) -> dict:
    """Parse a HAR file and extract endpoints.
    
    Args:
        file_path: Path to the HAR file.
        
    Returns:
        Dictionary containing parsed endpoints.
        
    Raises:
        FileNotFoundError: If file_path does not exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    pass
```

### TypeScript/React

- Use ESLint configuration
- Prefer functional components with hooks
- Use TypeScript strict mode
- Document complex logic with comments

```typescript
interface Endpoint {
  id: string;
  path: string;
  method: HTTPMethod;
  status: number;
}

function EndpointCard({ endpoint }: { endpoint: Endpoint }): JSX.Element {
  // Implementation
}
```

### General Principles

- Write readable, maintainable code
- Keep functions small and focused
- Avoid premature optimization
- Remove dead code
- Handle errors gracefully

## Testing Guidelines

### Running Tests

```bash
# All tests
pytest tests/

# Specific file
pytest tests/test_parser.py

# With coverage
pytest --cov=src tests/
```

### Writing Tests

- Write tests for all new features
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)
- Test edge cases and error conditions

```python
def test_parse_har_with_invalid_json():
    """Test that parser handles invalid JSON gracefully."""
    # Arrange
    invalid_file = "test_data/invalid.har"
    
    # Act & Assert
    with pytest.raises(json.JSONDecodeError):
        parse_har(invalid_file)
```

## Documentation

### Code Documentation

- Document all public APIs
- Keep docstrings up to date
- Include usage examples

### Project Documentation

- Update README.md for user-facing changes
- Update CHANGELOG.md for all changes
- Update API reference for endpoint changes

## Questions?

Feel free to open an issue with the `question` label or reach out to the maintainers.

---

Thank you for contributing to MockClaw!
