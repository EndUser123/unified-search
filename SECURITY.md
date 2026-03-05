# Security Policy

## Supported Versions

Currently supported versions:
- Version 0.1.x (development)

## Reporting a Vulnerability

If you discover a security vulnerability, please send an email to the project maintainers privately. Do NOT open a public issue.

**Email:** security@example.com (replace with actual contact)

Please include:
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Suggested fix (if known)

## What Happens Next?

1. We will acknowledge receipt of your report within 48 hours
2. We will investigate the vulnerability
3. We will provide a timeline for the fix
4. We will notify you when the fix is released
5. You will be credited in the release notes (unless you prefer anonymity)

## Security Best Practices

### For Users

- Keep dependencies updated
- Review the code before installing in production
- Use virtual environments to isolate dependencies
- Do not run with unnecessary permissions

### For Developers

- Validate all user inputs
- Use parameterized queries to prevent injection
- Follow secure coding guidelines (OWASP Top 10)
- Run security linters (bandit, safety)
- Keep dependencies updated

## Known Security Considerations

### Query Injection

The search-knowledge package processes user queries. While we don't use SQL directly, we validate all query inputs to prevent injection attacks.

### File Access

The package may access files specified by environment variables. Ensure:
- Database paths are not world-writable
- JSONL directories have restricted permissions
- Named pipes use secure permissions

### Dependencies

This package uses:
- Pydantic for data validation
- Click for CLI input handling
- Structlog for logging

All dependencies are regularly updated for security patches.

## Disclosure Policy

We follow responsible disclosure:
- Private report → Verify → Fix → Release → Credit
- Typical timeline: 7-14 days from report to fix
- Critical vulnerabilities: Faster response
- Full disclosure after fix is released

## Security Audits

This package has not yet undergone a formal security audit. Contributions from security researchers are welcome.

## License

Security vulnerabilities are disclosed under the MIT License terms.
