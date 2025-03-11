# Contributing to Mattermost MCP Host

Thank you for your interest in contributing to Mattermost MCP Host! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and constructive in all interactions.

## Getting Started

1. **Fork the Repository**
   - Fork the repository to your GitHub account
   - Clone your fork locally: `git clone <your-fork-url>`

2. **Set Up Development Environment**
   ```bash
   cd mattermost-mcp-host
   uv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   uv sync
   ```

3. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Guidelines

### Code Style
- Follow PEP 8 style guide for Python code
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Include type hints where appropriate
- Keep functions focused and modular

### Testing
- Write unit tests for new features
- Ensure all tests pass before submitting PR
- Run tests using: `pytest`
- Aim for high test coverage

### Documentation
- Update documentation for any new features
- Include docstrings and comments in code
- Update README.md if necessary
- Keep INSTALLATION.md current

### Commit Messages
- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, etc.)
- Reference issue numbers when applicable

## Pull Request Process

1. **Update Documentation**
   - Update relevant documentation
   - Add/update docstrings and comments
   - Update README if needed

2. **Test Your Changes**
   - Run the full test suite
   - Add new tests as needed
   - Ensure code coverage remains high

3. **Submit Pull Request**
   - Create PR against the `main` branch
   - Fill out the PR template completely
   - Reference any related issues
   - Provide clear description of changes

4. **Code Review**
   - Address review feedback promptly
   - Keep discussions constructive
   - Make requested changes as needed

## Issue Reporting

- Check existing issues before creating new ones
- Use issue templates when available
- Provide clear reproduction steps
- Include relevant system information
- Add labels as appropriate

## License

By contributing to Mattermost MCP Host, you agree that your contributions will be licensed under the MIT License.

## Questions or Need Help?

Feel free to:
- Open an issue for questions
- Join our community discussions
- Reach out to maintainers

Thank you for contributing to Mattermost MCP Host!
