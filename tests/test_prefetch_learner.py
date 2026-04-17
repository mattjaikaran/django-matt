"""Tests for predictive prefetching learner."""

from __future__ import annotations

import pytest

from django_matt.prefetch.learner import AccessPatternLearner


class TestAccessPatternLearner:
    def test_no_observations(self):
        learner = AccessPatternLearner()
        assert learner.suggest_prefetches("myapp.User") == []

    def test_single_observation(self):
        learner = AccessPatternLearner(threshold=0.5)
        learner.observe("myapp.User", ["organization", "profile"])
        suggestions = learner.suggest_prefetches("myapp.User")
        assert len(suggestions) == 2
        assert all(freq == 1.0 for _, freq in suggestions)

    def test_frequency_calculation(self):
        learner = AccessPatternLearner(threshold=0.3)
        learner.observe("myapp.User", ["organization", "profile"])
        learner.observe("myapp.User", ["organization"])
        learner.observe("myapp.User", ["organization"])

        suggestions = learner.suggest_prefetches("myapp.User")
        suggestion_dict = dict(suggestions)

        assert suggestion_dict["organization"] == 1.0
        assert suggestion_dict["profile"] == pytest.approx(0.333, abs=0.01)

    def test_threshold_filtering(self):
        learner = AccessPatternLearner(threshold=0.5)
        # org accessed 3/3, profile 1/3
        learner.observe("myapp.User", ["organization", "profile"])
        learner.observe("myapp.User", ["organization"])
        learner.observe("myapp.User", ["organization"])

        suggestions = learner.suggest_prefetches("myapp.User")
        names = [name for name, _ in suggestions]
        assert "organization" in names
        assert "profile" not in names  # 33% < 50%

    def test_max_prefetches(self):
        learner = AccessPatternLearner(threshold=0.0, max_prefetches=2)
        learner.observe("myapp.User", ["a", "b", "c", "d", "e"])
        suggestions = learner.suggest_prefetches("myapp.User")
        assert len(suggestions) == 2

    def test_independent_models(self):
        learner = AccessPatternLearner()
        learner.observe("myapp.User", ["org"])
        learner.observe("myapp.Order", ["product"])

        assert len(learner.suggest_prefetches("myapp.User")) == 1
        assert len(learner.suggest_prefetches("myapp.Order")) == 1
        assert learner.suggest_prefetches("myapp.User")[0][0] == "org"
        assert learner.suggest_prefetches("myapp.Order")[0][0] == "product"

    def test_get_stats(self):
        learner = AccessPatternLearner()
        learner.observe("myapp.User", ["org"])
        learner.observe("myapp.User", ["org", "profile"])
        stats = learner.get_stats("myapp.User")
        assert stats.total_observations == 2
        assert stats.relation_counts["org"] == 2
        assert stats.relation_counts["profile"] == 1

    def test_get_all_stats(self):
        learner = AccessPatternLearner()
        learner.observe("myapp.User", ["org"])
        learner.observe("myapp.Order", ["product"])
        all_stats = learner.get_all_stats()
        assert "myapp.User" in all_stats
        assert "myapp.Order" in all_stats

    def test_reset(self):
        learner = AccessPatternLearner()
        learner.observe("myapp.User", ["org"])
        learner.reset()
        assert learner.suggest_prefetches("myapp.User") == []

    def test_thread_safety(self):
        import threading

        learner = AccessPatternLearner()
        errors = []

        def observe_many():
            try:
                for _ in range(100):
                    learner.observe("myapp.User", ["org", "profile"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=observe_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = learner.get_stats("myapp.User")
        assert stats.total_observations == 400

    def test_sorted_by_frequency(self):
        learner = AccessPatternLearner(threshold=0.0)
        for _ in range(10):
            learner.observe("myapp.User", ["a"])
        for _ in range(5):
            learner.observe("myapp.User", ["b"])
        for _ in range(8):
            learner.observe("myapp.User", ["c"])

        suggestions = learner.suggest_prefetches("myapp.User")
        freqs = [f for _, f in suggestions]
        assert freqs == sorted(freqs, reverse=True)
