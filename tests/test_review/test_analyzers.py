from __future__ import annotations

import ast
from pathlib import Path

import pytest

from django_matt.review.config import ReviewConfig
from django_matt.review.analyzers.complexity import ComplexityAnalyzer
from django_matt.review.analyzers.solid import SolidAnalyzer
from django_matt.review.analyzers.django import DjangoBestPracticesAnalyzer
from django_matt.review.analyzers.ai_friendly import AIFriendlyAnalyzer
from django_matt.review.analyzers.security import SecurityAnalyzer
from django_matt.review.analyzers.modularity import ModularityAnalyzer
from django_matt.review.analyzers.performance import PerformanceAnalyzer


def _analyze(analyzer_cls: type, source: str, *, file_path: str = "test.py", **config_kwargs) -> list:
    tree = ast.parse(source)
    config = ReviewConfig(**config_kwargs)
    analyzer = analyzer_cls(config)
    return analyzer.analyze_file(Path(file_path), tree, source)


def _rule_ids(findings: list) -> set[str]:
    return {f.rule_id for f in findings}


# ═══════════════════════════════════════════════════════════════════════
# ComplexityAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestComplexityAnalyzer:
    def test_cx001_high_cyclomatic(self):
        branches = "\n".join(f"    if x == {i}: pass" for i in range(15))
        source = f"def complex_func(x):\n{branches}\n"
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX001" for f in findings)

    def test_cx002_high_cognitive(self):
        # Deeply nested logic raises cognitive complexity
        source = """
def nested(x):
    if x:
        for i in range(x):
            if i > 0:
                while i > 0:
                    if i % 2:
                        for j in range(i):
                            if j > 0:
                                pass
                    i -= 1
"""
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX002" for f in findings)

    def test_cx003_function_too_long(self):
        lines = ["def long_func():"]
        for i in range(60):
            lines.append(f"    x_{i} = {i}")
        source = "\n".join(lines) + "\n"
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX003" for f in findings)

    def test_cx004_class_too_long(self):
        lines = ["class BigClass:"]
        for i in range(310):
            lines.append(f"    attr_{i} = {i}")
        source = "\n".join(lines) + "\n"
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX004" for f in findings)

    def test_cx005_deep_nesting(self):
        source = """
def deep():
    if True:
        for i in range(10):
            while True:
                if i:
                    with open("f"):
                        pass
"""
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX005" for f in findings)

    def test_cx006_too_many_parameters(self):
        source = """
def many_params(a, b, c, d, e, f, g, h):
    pass
"""
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX006" for f in findings)

    def test_cx006_self_excluded(self):
        source = """
class Foo:
    def method(self, a, b, c):
        pass
"""
        findings = _analyze(ComplexityAnalyzer, source)
        assert not any(f.rule_id == "CX006" for f in findings)

    def test_cx007_too_many_returns(self):
        source = """
def many_returns(x):
    if x == 1:
        return 1
    if x == 2:
        return 2
    if x == 3:
        return 3
    if x == 4:
        return 4
    return 0
"""
        findings = _analyze(ComplexityAnalyzer, source)
        assert any(f.rule_id == "CX007" for f in findings)

    def test_clean_function_no_findings(self):
        source = """
def simple(x: int) -> int:
    return x + 1
"""
        findings = _analyze(ComplexityAnalyzer, source)
        assert findings == []

    def test_cx001_error_severity_at_double_threshold(self):
        # Build a function with cyclomatic > 20 (double default threshold of 10)
        branches = "\n".join(f"    if x == {i}: pass" for i in range(25))
        source = f"def mega(x):\n{branches}\n"
        findings = _analyze(ComplexityAnalyzer, source)
        cx001 = [f for f in findings if f.rule_id == "CX001"]
        assert len(cx001) >= 1
        from django_matt.review.findings import Severity
        assert cx001[0].severity == Severity.ERROR


# ═══════════════════════════════════════════════════════════════════════
# SolidAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestSolidAnalyzer:
    def test_sol001_too_many_public_methods(self):
        methods = "\n".join(f"    def method_{i}(self): pass" for i in range(20))
        source = f"class Bloated:\n{methods}\n"
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL001" for f in findings)

    def test_sol002_mixed_responsibilities(self):
        source = """
class MixedUp:
    def save_to_db(self): pass
    def calculate_total(self): pass
    def serialize_data(self): pass
"""
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL002" for f in findings)

    def test_sol003_excessive_type_checking(self):
        checks = "\n".join(f"    if isinstance(x, Type{i}): pass" for i in range(5))
        source = f"def dispatcher(x):\n{checks}\n"
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL003" for f in findings)

    def test_sol004_fat_interface(self):
        methods = "\n".join(
            f"    @abstractmethod\n    def method_{i}(self): ..." for i in range(12)
        )
        source = f"from abc import ABC, abstractmethod\nclass FatProtocol(ABC):\n{methods}\n"
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL004" for f in findings)

    def test_sol005_concrete_dependencies(self):
        params = ", ".join(f"dep{i}: ConcreteService{i}" for i in range(10))
        source = f"""
class TooManyDeps:
    def __init__(self, {params}):
        pass
"""
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL005" for f in findings)

    def test_sol006_god_class(self):
        # Needs method_count > max_class_methods * 2 (30) AND lines > max_class_lines (300)
        methods = []
        for i in range(35):
            body = "\n".join(f"        x_{j} = {j}" for j in range(10))
            methods.append(f"    def method_{i}(self):\n{body}")
        source = "class GodClass:\n" + "\n".join(methods) + "\n"
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL006" for f in findings)

    def test_clean_class_no_findings(self):
        source = """
class Simple:
    def __init__(self):
        self.value = 0

    def get_value(self):
        return self.value
"""
        findings = _analyze(SolidAnalyzer, source)
        assert findings == []

    def test_sol003_type_comparison_also_counted(self):
        source = """
def check(obj):
    if obj.type == "a": pass
    if obj.type == "b": pass
    if obj.kind == "c": pass
    if obj.tag == "d": pass
"""
        findings = _analyze(SolidAnalyzer, source)
        assert any(f.rule_id == "SOL003" for f in findings)


# ═══════════════════════════════════════════════════════════════════════
# DjangoBestPracticesAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestDjangoAnalyzer:
    def test_dj001_sync_orm_in_async(self):
        source = """
async def my_view(request):
    user = User.objects.get(pk=1)
    return user
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ001" for f in findings)

    def test_dj002_n_plus_one(self):
        source = """
def process():
    for item in items:
        related = item.objects.filter(active=True)
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ002" for f in findings)

    def test_dj003_fat_view(self):
        lines = ["def my_view(request):"]
        for i in range(55):
            lines.append(f"    x_{i} = {i}")
        source = "\n".join(lines) + "\n"
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ003" for f in findings)

    def test_dj004_raw_sql_injection(self):
        source = """
def get_data(name):
    User.objects.raw(f"SELECT * FROM users WHERE name = '{name}'")
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ004" for f in findings)

    def test_dj004_raw_sql_warning(self):
        source = """
def get_data():
    User.objects.raw("SELECT * FROM users")
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        dj004 = [f for f in findings if f.rule_id == "DJ004"]
        assert len(dj004) >= 1
        from django_matt.review.findings import Severity
        assert dj004[0].severity == Severity.WARNING

    def test_dj005_missing_auth_on_view_class(self):
        source = """
class UserController(APIView):
    def get(self, request):
        pass
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ005" for f in findings)

    def test_dj005_auth_present_no_finding(self):
        source = """
class UserController(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pass
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert not any(f.rule_id == "DJ005" for f in findings)

    def test_dj001_sync_in_sync_no_finding(self):
        source = """
def my_view(request):
    user = User.objects.get(pk=1)
    return user
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert not any(f.rule_id == "DJ001" for f in findings)

    def test_dj006_business_logic_in_view(self):
        source = """
def my_view(request):
    Product.objects.create(name="test", price=10)
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ006" for f in findings)

    def test_dj007_unbounded_queryset(self):
        source = """
def my_view(request):
    items = Item.objects.all()
"""
        findings = _analyze(DjangoBestPracticesAnalyzer, source)
        assert any(f.rule_id == "DJ007" for f in findings)


# ═══════════════════════════════════════════════════════════════════════
# AIFriendlyAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestAIFriendlyAnalyzer:
    def test_ai001_file_too_large(self):
        lines = [f"x_{i} = {i}" for i in range(510)]
        source = "\n".join(lines) + "\n"
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI001" for f in findings)

    def test_ai002_function_too_long(self):
        body = "\n".join(f"    x_{i} = {i}" for i in range(50))
        source = f'"""Module doc."""\ndef long_func():\n{body}\n'
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI002" for f in findings)

    def test_ai003_low_type_hint_coverage(self):
        funcs = "\n".join(f"def func_{i}(a, b): return a" for i in range(10))
        source = f'"""Module doc."""\n{funcs}\n'
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI003" for f in findings)

    def test_ai003_full_coverage_no_finding(self):
        funcs = "\n".join(f"def func_{i}(a: int, b: int) -> int: return a" for i in range(5))
        source = f'"""Module doc."""\n{funcs}\n'
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert not any(f.rule_id == "AI003" for f in findings)

    def test_ai004_poor_naming_clarity(self):
        # Many short meaningless variable names
        assigns = "\n".join(f"ab = {i}" for i in range(20))
        source = f'"""Module doc."""\n{assigns}\n'
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI004" for f in findings)

    def test_ai005_deep_nesting(self):
        source = '''"""Module doc."""
def deep():
    if True:
        for i in range(10):
            while True:
                if i:
                    pass
'''
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI005" for f in findings)

    def test_ai006_magic_literal(self):
        source = '''"""Module doc."""
def check(x):
    if x == 42:
        return True
'''
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI006" for f in findings)

    def test_ai006_non_magic_number_no_finding(self):
        source = '''"""Module doc."""
def check(x: int) -> bool:
    if x == 200:
        return True
    return False
'''
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert not any(f.rule_id == "AI006" for f in findings)

    def test_ai007_missing_module_docstring(self):
        source = """
def hello():
    pass
"""
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert any(f.rule_id == "AI007" for f in findings)

    def test_ai007_has_docstring_no_finding(self):
        source = '''"""This module does things."""

def hello():
    pass
'''
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert not any(f.rule_id == "AI007" for f in findings)

    def test_clean_file_no_findings(self):
        source = '''"""Well documented module."""

def greet(name: str) -> str:
    return f"Hello, {name}"
'''
        findings = _analyze(AIFriendlyAnalyzer, source)
        assert findings == []


# ═══════════════════════════════════════════════════════════════════════
# SecurityAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestSecurityAnalyzer:
    def test_sec001_hardcoded_secret(self):
        source = """
password = "super_secret_123"
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC001" for f in findings)

    def test_sec001_comment_ignored(self):
        source = """
# password = "not_a_real_secret"
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert not any(f.rule_id == "SEC001" for f in findings)

    def test_sec002_sql_injection_fstring(self):
        source = """
def get_user(name):
    cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC002" for f in findings)

    def test_sec002_sql_injection_format(self):
        source = """
def get_user(name):
    cursor.execute("SELECT * FROM users WHERE name = '{}'".format(name))
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC002" for f in findings)

    def test_sec003_eval_with_variable(self):
        source = """
def run(code):
    eval(code)
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC003" for f in findings)

    def test_sec003_eval_with_literal_no_finding(self):
        source = """
def run():
    eval("1 + 1")
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert not any(f.rule_id == "SEC003" for f in findings)

    def test_sec004_pickle_loads(self):
        source = """
import pickle
def load_data(data):
    return pickle.loads(data)
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC004" for f in findings)

    def test_sec004_yaml_load_unsafe(self):
        source = """
import yaml
def load_config(stream):
    return yaml.load(stream)
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC004" for f in findings)

    def test_sec004_yaml_safe_loader_no_finding(self):
        source = """
import yaml
def load_config(stream):
    return yaml.load(stream, Loader=yaml.SafeLoader)
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert not any(f.rule_id == "SEC004" for f in findings)

    def test_sec005_open_redirect(self):
        source = """
def my_view(request):
    return redirect(request.GET.get("next"))
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC005" for f in findings)

    def test_sec006_csrf_exempt(self):
        source = """
@csrf_exempt
def my_view(request):
    pass
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC006" for f in findings)

    def test_sec007_debug_true_in_settings(self):
        source = """
DEBUG = True
"""
        findings = _analyze(SecurityAnalyzer, source, file_path="settings.py")
        assert any(f.rule_id == "SEC007" for f in findings)

    def test_sec007_debug_in_non_settings_no_finding(self):
        source = """
DEBUG = True
"""
        findings = _analyze(SecurityAnalyzer, source, file_path="views.py")
        assert not any(f.rule_id == "SEC007" for f in findings)

    def test_sec008_weak_crypto(self):
        source = """
import hashlib
def hash_password(pw):
    return hashlib.md5(pw.encode())
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert any(f.rule_id == "SEC008" for f in findings)

    def test_clean_code_no_findings(self):
        source = """
def safe_func(data: str) -> str:
    return data.strip()
"""
        findings = _analyze(SecurityAnalyzer, source)
        assert findings == []


# ═══════════════════════════════════════════════════════════════════════
# ModularityAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestModularityAnalyzer:
    def test_mod001_too_many_imports(self):
        imports = "\n".join(f"import module_{i}" for i in range(20))
        source = imports + "\n"
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD001" for f in findings)

    def test_mod002_star_import(self):
        source = """
from os.path import *
"""
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD002" for f in findings)

    def test_mod003_circular_import_risk(self):
        source = """
def lazy_load():
    import something
"""
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD003" for f in findings)

    def test_mod004_god_module(self):
        defs = "\n".join(f"def func_{i}(): pass" for i in range(12))
        source = defs + "\n"
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD004" for f in findings)

    def test_mod005_deep_import_path(self):
        source = """
from a.b.c.d.e import something
"""
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD005" for f in findings)

    def test_mod005_deep_import_statement(self):
        source = """
import a.b.c.d.e
"""
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD005" for f in findings)

    def test_mod006_mixed_abstraction_levels(self):
        methods = "\n".join(f"    def m_{i}(self): pass" for i in range(6))
        source = f"class Big:\n{methods}\n\ndef standalone(): pass\n"
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD006" for f in findings)

    def test_mod007_missing_dunder_all(self):
        defs = "\n".join(f"def func_{i}(): pass" for i in range(4))
        source = defs + "\n"
        findings = _analyze(ModularityAnalyzer, source)
        assert any(f.rule_id == "MOD007" for f in findings)

    def test_mod007_init_file_skipped(self):
        defs = "\n".join(f"def func_{i}(): pass" for i in range(4))
        source = defs + "\n"
        findings = _analyze(ModularityAnalyzer, source, file_path="__init__.py")
        assert not any(f.rule_id == "MOD007" for f in findings)

    def test_mod007_dunder_all_present_no_finding(self):
        source = """
__all__ = ["func_a", "func_b", "func_c"]

def func_a(): pass
def func_b(): pass
def func_c(): pass
"""
        findings = _analyze(ModularityAnalyzer, source)
        assert not any(f.rule_id == "MOD007" for f in findings)

    def test_clean_module_no_findings(self):
        source = """
import os

def helper():
    pass
"""
        findings = _analyze(ModularityAnalyzer, source)
        assert findings == []


# ═══════════════════════════════════════════════════════════════════════
# PerformanceAnalyzer
# ═══════════════════════════════════════════════════════════════════════


class TestPerformanceAnalyzer:
    def test_perf001_orm_in_loop(self):
        source = """
def process(items):
    for item in items:
        result = Item.objects.filter(pk=item.pk)
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF001" for f in findings)

    def test_perf002_len_on_queryset(self):
        source = """
def count_items():
    total = len(items_qs)
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF002" for f in findings)

    def test_perf002_len_on_filter_result(self):
        source = """
def count_items():
    total = len(Item.objects.filter(active=True))
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF002" for f in findings)

    def test_perf003_blocking_io_in_async(self):
        source = """
import time
async def slow():
    time.sleep(1)
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF003" for f in findings)

    def test_perf003_blocking_requests_in_async(self):
        source = """
import requests
async def fetch():
    requests.get("https://example.com")
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF003" for f in findings)

    def test_perf003_sync_function_no_finding(self):
        source = """
import time
def slow():
    time.sleep(1)
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert not any(f.rule_id == "PERF003" for f in findings)

    def test_perf006_string_concat_in_loop(self):
        source = """
def build():
    html = ""
    for i in range(10):
        html += "<p>item</p>"
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF006" for f in findings)

    def test_perf007_mutable_default(self):
        source = """
def append_to(item, target=[]):
    target.append(item)
    return target
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF007" for f in findings)

    def test_perf007_mutable_default_dict(self):
        source = """
def merge(data, base={}):
    base.update(data)
    return base
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF007" for f in findings)

    def test_perf007_none_default_no_finding(self):
        source = """
def append_to(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert not any(f.rule_id == "PERF007" for f in findings)

    def test_clean_code_no_findings(self):
        source = """
def simple(x: int) -> int:
    return x + 1
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert findings == []

    def test_perf005_queryset_reevaluation(self):
        source = """
def process():
    qs = Item.objects.filter(active=True)
    first = qs[0]
    count = qs.count()
    last = qs.last()
"""
        findings = _analyze(PerformanceAnalyzer, source)
        assert any(f.rule_id == "PERF005" for f in findings)
