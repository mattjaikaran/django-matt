"""
Client adapters for Django Matt Pages.

These modules generate the client-side code for each framework
that can be used to build the SPA.
"""

from django_matt.pages.adapters.react import generate_react_adapter
from django_matt.pages.adapters.svelte import generate_svelte_adapter
from django_matt.pages.adapters.solid import generate_solid_adapter

__all__ = [
    "generate_react_adapter",
    "generate_svelte_adapter",
    "generate_solid_adapter",
]
