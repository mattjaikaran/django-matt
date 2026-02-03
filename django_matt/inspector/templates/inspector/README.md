# Inspector Templates

These templates are optional. The inspector dashboard includes embedded HTML by default
for zero-configuration usage.

To use custom templates instead of embedded HTML:

1. Add `django_matt.inspector` to `INSTALLED_APPS`
2. Override templates in your project's templates directory:
   - `inspector/base.html` - Base template
   - `inspector/dashboard.html` - Main dashboard
   - `inspector/detail.html` - Request detail view

Template context variables:
- `requests` - List of CapturedRequest objects
- `request` - Current request detail (in detail view)
- `stats` - Inspector statistics dict
- `is_capturing` - Boolean indicating if capture is active
