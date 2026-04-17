"""Predictive prefetching — learn access patterns and auto-optimize querysets."""

from django_matt.prefetch.learner import AccessPatternLearner
from django_matt.prefetch.middleware import PredictivePrefetchMiddleware

__all__ = [
    "AccessPatternLearner",
    "PredictivePrefetchMiddleware",
]
