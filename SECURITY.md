# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.10.x  | :white_check_mark: |
| 0.9.x   | :white_check_mark: |
| < 0.9   | :x:                |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Instead, please report them privately:

1. **GitHub Security Advisories** (preferred): Go to [Security > Advisories](https://github.com/mattjaikaran/django-matt/security/advisories) and click "Report a vulnerability"
2. **Email**: Send details to security@mattjaikaran.com

### What to include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

### Response timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix timeline**: Depends on severity; critical issues are prioritized immediately

### After reporting

- You will receive a confirmation with a tracking reference
- We will work with you to understand and validate the issue
- A fix will be developed and tested privately before disclosure
- You will be credited in the advisory (unless you prefer anonymity)

## Security Best Practices

When using django-matt in production:

- Keep `SECRET_KEY` and credentials out of source control — use the `secrets` module with a proper backend (Vault, AWS SM, etc.)
- Enable HTTPS and set `SECURE_SSL_REDIRECT = True`
- Use the built-in rate limiting (`throttling` module) on authentication endpoints
- Review `django.middleware.security.SecurityMiddleware` settings
- Run `python manage.py check --deploy` before deploying
