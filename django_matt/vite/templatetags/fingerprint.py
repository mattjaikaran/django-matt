"""
Template tags for static file fingerprinting.

Usage:
    {% load fingerprint %}
    <link rel="stylesheet" href="{% fingerprint 'css/style.css' %}">
    <script src="{% fingerprint 'js/app.js' %}"></script>
"""

from django import template
from django.templatetags.static import static

from django_matt.vite.fingerprint import get_manifest

register = template.Library()


@register.simple_tag
def fingerprint(name: str) -> str:
    """
    Resolve a static file to its fingerprinted URL.

    Falls back to the standard static URL if no fingerprint is available.
    """
    manifest = get_manifest()
    resolved = manifest.resolve(name)
    return static(resolved)
