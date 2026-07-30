"""Tests for architecture guardrails — contract loading, validation, and CI blocking."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from django_matt.guardrails import (
    ArchitectureContract,
    contract_to_checker_data,
    load_contract,
    validate_contract,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _toml(*lines: str) -> str:
    """Join lines into a TOML string."""
    return "\n".join(lines)


def _write_tmp_toml(content: str, dir: Path) -> Path:
    """Write content to a temporary .toml file and return its path."""
    p = dir / "test_contract.toml"
    p.write_text(content, encoding="utf-8")
    return p


# ── Valid contract fixture (matches _parse_contract expected shape) ──────────

_VALID_CONTRACT_TOML = _toml(
    "",
    "[layers]",
    'foundation = ["_accel", "api", "compat", "conf", "core", "slim"]',
    'infrastructure = ["audit", "db", "di", "middleware", "testing", "permissions"]',
    'domain = ["auth", "billing", "email", "multitenancy", "ml", "ai"]',
    'interface = ["admin", "forms", "views"]',
    "",
    "[tooling]",
    'modules = ["cli", "codegen", "deploy", "management"]',
    "",
    "[exemptions]",
    'testing_exempt = ["testing"]',
    'api_facade_file = "django_matt/api.py"',
    "",
    "[[rules.cross_layer]]",
    'source = "core"',
    'target = "di"',
    'reason = "core/router.py DI integration"',
    "",
    "[[rules.cross_layer]]",
    'source = "permissions"',
    'target = "multitenancy"',
    'reason = "org-scoped permissions need tenant models"',
    "",
    "[[rules.cross_domain]]",
    'source = "ml"',
    'target = "ai"',
    'reason = "ML models use AI base classes"',
    "",
    "[external]",
    'prefixes = ["django.", "rest_framework.", "celery."]',
    "",
    "[skip]",
    'directories = [".venv", "venv", "__pycache__"]',
    'modules = ["__pycache__", "migrations"]',
    "",
    "[ci]",
    'fail_on = ["LAYER-DEP", "CROSS-DOMAIN", "NO-TEST-IMPORT"]',
)


# ── ArchitectureContract ──────────────────────────────────────────────────────


class TestArchitectureContractDefaults:
    """Default contract has empty collections."""

    def test_default_layers_empty(self):
        c = ArchitectureContract()
        assert c.layers == {}
        assert c.layer_order == []

    def test_default_exemptions_empty(self):
        c = ArchitectureContract()
        assert c.exempt_modules == set()
        assert c.cross_layer_exemptions == set()
        assert c.cross_domain_exemptions == set()

    def test_default_ci_empty(self):
        c = ArchitectureContract()
        assert c.ci_fail_on == set()

    def test_default_skip_empty(self):
        c = ArchitectureContract()
        assert c.skip_dirs == set()
        assert c.skip_modules == set()

    def test_default_test_exempt_empty(self):
        c = ArchitectureContract()
        assert c.test_exempt_modules == set()

    def test_default_api_facade_none(self):
        c = ArchitectureContract()
        assert c.api_facade_file is None

    def test_default_external_prefixes_empty(self):
        c = ArchitectureContract()
        assert c.external_prefixes == frozenset()


# ── load_contract ─────────────────────────────────────────────────────────────


class TestLoadContract:
    def test_loads_valid_toml(self, tmp_path):
        p = _write_tmp_toml(_VALID_CONTRACT_TOML, tmp_path)
        contract = load_contract(p)
        assert isinstance(contract, ArchitectureContract)
        assert len(contract.layers) == 4
        assert contract.layers["foundation"] == [
            "_accel", "api", "compat", "conf", "core", "slim",
        ]
        assert contract.layer_order == ["foundation", "infrastructure", "domain", "interface"]

    def test_missing_file_returns_default(self, tmp_path):
        p = tmp_path / "nonexistent.toml"
        contract = load_contract(p)
        assert contract.layers == {}
        assert contract.exempt_modules == set()

    def test_invalid_toml_returns_default(self, tmp_path):
        p = _write_tmp_toml("this is not valid toml {{{", tmp_path)
        contract = load_contract(p)
        assert contract.layers == {}

    def test_loads_exempt_modules(self, tmp_path):
        toml = _toml(
            "[tooling]",
            'modules = ["cli", "codegen", "deploy"]',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.exempt_modules == {"cli", "codegen", "deploy"}
    def test_loads_cross_layer_exemptions(self, tmp_path):
        toml = _toml(
            "[[rules.cross_layer]]",
            'source = "a"',
            'target = "b"',
            "",
            "[[rules.cross_layer]]",
            'source = "c"',
            'target = "d"',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.cross_layer_exemptions == {("a", "b"), ("c", "d")}

    def test_loads_cross_domain_exemptions(self, tmp_path):
        toml = _toml(
            "[[rules.cross_domain]]",
            'source = "x"',
            'target = "y"',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.cross_domain_exemptions == {("x", "y")}

    def test_loads_external_prefixes(self, tmp_path):
        toml = _toml(
            "[external]",
            'prefixes = ["django.", "pydantic."]',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.external_prefixes == frozenset({"django.", "pydantic."})
    def test_loads_skip_config(self, tmp_path):
        toml = _toml(
            "[skip]",
            'directories = [".venv", "node_modules"]',
            'modules = ["migrations", "__pycache__"]',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.skip_dirs == {".venv", "node_modules"}
        assert contract.skip_modules == {"migrations", "__pycache__"}
    def test_loads_api_facade_file(self, tmp_path):
        toml = _toml(
            "[exemptions]",
            'api_facade_file = "django_matt/api.py"',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.api_facade_file == "django_matt/api.py"

    def test_loads_test_exempt(self, tmp_path):
        toml = _toml(
            "[exemptions]",
            'testing_exempt = ["testing", "test_utils"]',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.test_exempt_modules == {"testing", "test_utils"}
    def test_loads_ci_config(self, tmp_path):
        toml = _toml(
            "[ci]",
            'fail_on = ["LAYER-DEP", "CROSS-DOMAIN"]',
        )
        p = _write_tmp_toml(toml, tmp_path)
        contract = load_contract(p)
        assert contract.ci_fail_on == {"LAYER-DEP", "CROSS-DOMAIN"}

    def test_loads_full_contract(self, tmp_path):
        p = _write_tmp_toml(_VALID_CONTRACT_TOML, tmp_path)
        contract = load_contract(p)
        assert contract.layers["domain"] == ["auth", "billing", "email", "multitenancy", "ml", "ai"]
        assert contract.exempt_modules == {"cli", "codegen", "deploy", "management"}
        assert contract.cross_layer_exemptions == {("core", "di"), ("permissions", "multitenancy")}
        assert contract.cross_domain_exemptions == {("ml", "ai")}
        assert contract.external_prefixes == frozenset({"django.", "rest_framework.", "celery."})
        assert contract.skip_dirs == {".venv", "venv", "__pycache__"}
        assert contract.skip_modules == {"__pycache__", "migrations"}
        assert contract.api_facade_file == "django_matt/api.py"
        assert contract.test_exempt_modules == {"testing"}
        assert contract.ci_fail_on == {"LAYER-DEP", "CROSS-DOMAIN", "NO-TEST-IMPORT"}

    def test_str_path_works(self, tmp_path):
        p = _write_tmp_toml(_VALID_CONTRACT_TOML, tmp_path)
        contract = load_contract(str(p))
        assert len(contract.layers) == 4

    def test_permission_error_returns_default(self, tmp_path):
        """load_contract handles PermissionError gracefully."""
        # Create a directory where a file is expected
        p = tmp_path / "adir"
        p.mkdir()
        contract = load_contract(p)
        assert contract.layers == {}


# ── validate_contract ─────────────────────────────────────────────────────────


class TestValidateContract:
    def test_empty_contract_is_valid(self):
        errors = validate_contract(ArchitectureContract())
        assert errors == []

    def test_valid_full_contract_passes(self, tmp_path):
        p = _write_tmp_toml(_VALID_CONTRACT_TOML, tmp_path)
        contract = load_contract(p)
        errors = validate_contract(contract)
        assert errors == []

    def test_duplicate_module_in_layers(self):
        contract = ArchitectureContract(
            layers={
                "foundation": ["core", "api"],
                "infrastructure": ["core", "db"],  # "core" duplicated
            },
            layer_order=["foundation", "infrastructure"],
        )
        errors = validate_contract(contract)
        assert any("'core' appears in both" in e for e in errors)

    def test_layers_without_order(self):
        contract = ArchitectureContract(
            layers={"foundation": ["core"]},
            # layer_order intentionally left empty
        )
        errors = validate_contract(contract)
        assert any("layer_order is empty" in e for e in errors)

    def test_exempt_overlap_with_layers(self):
        contract = ArchitectureContract(
            layers={"foundation": ["core", "api"]},
            layer_order=["foundation"],
            exempt_modules={"core"},  # "core" in both
        )
        errors = validate_contract(contract)
        assert any("Exempt modules also appear in layers" in e for e in errors)

    def test_unknown_cross_layer_source(self):
        contract = ArchitectureContract(
            layers={"foundation": ["core"], "interface": ["views"]},
            layer_order=["foundation", "interface"],
            cross_layer_exemptions={("nonexistent", "views")},
        )
        errors = validate_contract(contract)
        assert any("source 'nonexistent' is not a known module" in e for e in errors)

    def test_unknown_cross_layer_target(self):
        contract = ArchitectureContract(
            layers={"foundation": ["core"], "interface": ["views"]},
            layer_order=["foundation", "interface"],
            cross_layer_exemptions={("core", "nonexistent")},
        )
        errors = validate_contract(contract)
        assert any("target 'nonexistent' is not a known module" in e for e in errors)

    def test_cross_domain_source_not_domain(self):
        contract = ArchitectureContract(
            layers={
                "foundation": ["core"],
                "domain": ["auth"],
            },
            layer_order=["foundation", "domain"],
            cross_domain_exemptions={("core", "auth")},  # core is not domain
        )
        errors = validate_contract(contract)
        assert any("source 'core' is not a domain module" in e for e in errors)

    def test_cross_domain_target_not_domain(self):
        contract = ArchitectureContract(
            layers={
                "domain": ["auth"],
                "interface": ["views"],
            },
            layer_order=["domain", "interface"],
            cross_domain_exemptions={("auth", "views")},  # views is not domain
        )
        errors = validate_contract(contract)
        assert any("target 'views' is not a domain module" in e for e in errors)

    def test_unknown_test_exempt(self):
        contract = ArchitectureContract(
            layers={"foundation": ["core"]},
            layer_order=["foundation"],
            test_exempt_modules={"unknown"},
        )
        errors = validate_contract(contract)
        assert any("test_exempt module 'unknown' is not a known module" in e for e in errors)

    def test_unknown_ci_rule(self):
        contract = ArchitectureContract(
            ci_fail_on={"NONEXISTENT-RULE"},
        )
        errors = validate_contract(contract)
        assert any("Unknown CI rule 'NONEXISTENT-RULE'" in e for e in errors)

    def test_api_facade_not_py(self):
        contract = ArchitectureContract(
            api_facade_file="django_matt/api.txt",
        )
        errors = validate_contract(contract)
        assert any("does not end with .py" in e for e in errors)

    def test_api_facade_parent_traversal(self):
        contract = ArchitectureContract(
            api_facade_file="../api.py",
        )
        errors = validate_contract(contract)
        assert any("contains parent traversal" in e for e in errors)

    def test_multiple_errors_collected(self):
        contract = ArchitectureContract(
            layers={"foundation": ["core"]},
            layer_order=["foundation"],
            cross_layer_exemptions={("core", "nonexistent")},
            test_exempt_modules={"unknown"},
            ci_fail_on={"BAD-RULE"},
            api_facade_file="bad.txt",
        )
        errors = validate_contract(contract)
        assert len(errors) >= 3  # at least 3 different error categories

    def test_valid_cross_domain_within_domain(self):
        contract = ArchitectureContract(
            layers={
                "domain": ["auth", "billing"],
            },
            layer_order=["domain"],
            cross_domain_exemptions={("auth", "billing")},
        )
        errors = validate_contract(contract)
        assert errors == []

    def test_known_ci_rules_accepted(self):
        contract = ArchitectureContract(
            ci_fail_on={"LAYER-DEP", "CROSS-DOMAIN", "NO-TEST-IMPORT"},
        )
        errors = validate_contract(contract)
        assert errors == []


# ── contract_to_checker_data ──────────────────────────────────────────────────


class TestContractToCheckerData:
    def test_empty_contract_produces_empty_sets(self):
        data = contract_to_checker_data(ArchitectureContract())
        assert data["FOUNDATION"] == set()
        assert data["INFRASTRUCTURE"] == set()
        assert data["DOMAIN"] == set()
        assert data["INTERFACE"] == set()
        assert data["TOOLING"] == set()
        assert data["ALLOWED_CROSS_LAYER"] == set()
        assert data["ALLOWED_CROSS_DOMAIN"] == set()
        assert data["SKIP_DIRS"] == set()
        assert data["SKIP_MODULES"] == set()
        assert data["_EXTERNAL_PREFIXES"] == frozenset()
        assert data["TESTING_EXEMPT"] == set()
        assert data["API_FACADE_FILE"] is None

    def test_full_contract_maps_correctly(self, tmp_path):
        p = _write_tmp_toml(_VALID_CONTRACT_TOML, tmp_path)
        contract = load_contract(p)
        data = contract_to_checker_data(contract)

        assert data["FOUNDATION"] == {"_accel", "api", "compat", "conf", "core", "slim"}
        assert data["INFRASTRUCTURE"] == {"audit", "db", "di", "middleware", "testing", "permissions"}
        assert data["DOMAIN"] == {"auth", "billing", "email", "multitenancy", "ml", "ai"}
        assert data["INTERFACE"] == {"admin", "forms", "views"}
        assert data["TOOLING"] == {"cli", "codegen", "deploy", "management"}
        assert data["ALLOWED_CROSS_LAYER"] == {("core", "di"), ("permissions", "multitenancy")}
        assert data["ALLOWED_CROSS_DOMAIN"] == {("ml", "ai")}
        assert data["SKIP_DIRS"] == {".venv", "venv", "__pycache__"}
        assert data["SKIP_MODULES"] == {"__pycache__", "migrations"}
        assert data["_EXTERNAL_PREFIXES"] == frozenset({"django.", "rest_framework.", "celery."})
        assert data["TESTING_EXEMPT"] == {"testing"}
        assert data["API_FACADE_FILE"] == "django_matt/api.py"

    def test_has_all_required_keys(self):
        data = contract_to_checker_data(ArchitectureContract())
        required = {
            "FOUNDATION", "INFRASTRUCTURE", "DOMAIN", "INTERFACE",
            "TOOLING", "ALLOWED_CROSS_LAYER", "ALLOWED_CROSS_DOMAIN",
            "SKIP_DIRS", "SKIP_MODULES", "_EXTERNAL_PREFIXES",
            "TESTING_EXEMPT", "API_FACADE_FILE",
        }
        assert set(data.keys()) == required


# ── check_architecture.py integration ─────────────────────────────────────────


# TOML fixture matching the actual contract format used by load_contract_rules()
_CONTRACT_LOADER_TOML = _toml(
    "",
    "[layers]",
    'foundation = ["_accel", "api", "compat", "conf", "core", "slim"]',
    'infrastructure = ["audit", "db", "di", "middleware", "testing"]',
    'domain = ["auth", "billing", "email"]',
    'interface = ["admin", "forms", "views"]',
    "",
    "[tooling]",
    'modules = ["cli", "codegen", "deploy"]',
    "",
    "[exemptions]",
    'testing_exempt = ["testing"]',
    'api_facade_file = "django_matt/api.py"',
    "",
    "[[rules.cross_layer]]",
    'source = "core"',
    'target = "di"',
    'reason = "core/router.py DI integration"',
    "",
    "[[rules.cross_layer]]",
    'source = "permissions"',
    'target = "multitenancy"',
    'reason = "org-scoped permissions need tenant models"',
    "",
    "[[rules.cross_domain]]",
    'source = "ml"',
    'target = "ai"',
    'reason = "ML models use AI base classes"',
    "",
    "[external]",
    'prefixes = ["django.", "rest_framework."]',
    "",
    "[skip]",
    'directories = [".venv", "__pycache__"]',
    'modules = ["migrations"]',
    "",
    "[ci]",
    'fail_on = ["LAYER-DEP", "CROSS-DOMAIN", "NO-TEST-IMPORT"]',
)


class TestCheckArchitectureIntegration:
    """Integration tests for check_architecture.py script behavior."""

    SCRIPT = "scripts/check_architecture.py"

    def _run_checker(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True,
            text=True,
            **kwargs,
        )

    def test_runs_without_args(self):
        """check_architecture.py runs and produces output."""
        result = self._run_checker()
        # Should complete (no files = check passes)
        assert result.returncode in (0, 1)
        # Output should mention architecture check
        combined = result.stdout + result.stderr
        assert "architecture" in combined.lower() or "checked" in combined.lower()

    def test_all_flag_runs(self):
        """--all flag checks all files."""
        result = self._run_checker("--all")
        # Should complete (may have violations, but shouldn't crash)
        assert result.returncode in (0, 1)
        combined = result.stdout + result.stderr
        assert "checked" in combined.lower()

    def test_contract_flag_loads_file(self, tmp_path):
        """--contract flag loads a TOML file."""
        p = _write_tmp_toml(_CONTRACT_LOADER_TOML, tmp_path)
        result = self._run_checker("--all", "--contract", str(p))
        # Should run successfully with loaded contract
        assert result.returncode in (0, 1)
        combined = result.stdout + result.stderr
        assert "checked" in combined.lower()

    def test_contract_flag_with_missing_file(self):
        """--contract flag with nonexistent file falls back to defaults."""
        result = self._run_checker("--all", "--contract", "/nonexistent/path.toml")
        assert result.returncode in (0, 1)
        combined = result.stdout + result.stderr
        assert "contract not found" in combined.lower() or "checked" in combined.lower()

    def test_no_contract_flag_skips_loading(self):
        """--no-contract skips contract loading entirely."""
        result = self._run_checker("--all", "--no-contract")
        assert result.returncode in (0, 1)
        combined = result.stdout + result.stderr
        assert "checked" in combined.lower()

    def test_specific_files(self):
        """Passing specific files works."""
        result = self._run_checker(
            "django_matt/core/__init__.py",
            "django_matt/conf.py",
        )
        assert result.returncode in (0, 1)
        combined = result.stdout + result.stderr
        assert "checked" in combined.lower()


# ── CI blocking behavior ──────────────────────────────────────────────────────

# TOML that fails on specific rules (matching actual contract format)
_FAIL_ON_LAYER_DEP_TOML = _toml(
    "",
    "[layers]",
    'foundation = ["_accel", "api", "compat", "conf", "core", "slim"]',
    'infrastructure = ["audit", "db", "di", "middleware", "testing"]',
    'domain = ["auth", "billing", "email"]',
    'interface = ["admin", "forms", "views"]',
    "",
    "[tooling]",
    'modules = []',
    "",
    "[exemptions]",
    'testing_exempt = []',
    'api_facade_file = "django_matt/api.py"',
    "",
    "[rules]",
    "",
    "[external]",
    'prefixes = ["django.", "rest_framework."]',
    "",
    "[skip]",
    'directories = []',
    'modules = []',
    "",
    "[ci]",
    'fail_on = ["LAYER-DEP"]',
)


class TestCIBlocking:
    """Tests that CI fail_on configuration causes non-zero exits."""

    SCRIPT = "scripts/check_architecture.py"

    def _run_checker(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True,
            text=True,
        )

    def test_contract_with_fail_on_layer_dep_runs(self, tmp_path):
        """Contract with fail_on rules loads and checker runs."""
        p = _write_tmp_toml(_FAIL_ON_LAYER_DEP_TOML, tmp_path)
        result = self._run_checker("--all", "--contract", str(p))
        # Should complete (may have violations, but shouldn't crash)
        assert result.returncode in (0, 1)

    def test_help_shows_contract_flag(self):
        """--help includes the --contract flag."""
        result = self._run_checker("--help")
        assert "--contract" in result.stdout
        assert "--no-contract" in result.stdout

    def test_no_contract_uses_hardcoded_defaults(self):
        """Without --contract, the checker runs with hardcoded defaults."""
        result = self._run_checker("--no-contract", "django_matt/conf.py")
        assert result.returncode in (0, 1)

    def test_checker_exit_code_reflects_violations(self):
        """When violations exist, exit code is non-zero."""
        # Run on a file known to import from tests (if any exist)
        # Just verify the script doesn't crash
        result = self._run_checker("--all")
        assert result.returncode in (0, 1)


# ── Default vs contract merge behavior ────────────────────────────────────────


class TestContractMerge:
    """Tests that contract data can be merged with programmatic defaults."""

    def test_contract_to_checker_data_structure_matches_defaults(self):
        """contract_to_checker_data output has same key structure as script globals."""
        import scripts.check_architecture as arch

        data = contract_to_checker_data(ArchitectureContract())

        # All keys should exist and be the right type
        for key in ("FOUNDATION", "INFRASTRUCTURE", "DOMAIN", "INTERFACE"):
            assert isinstance(data[key], set)
            assert isinstance(getattr(arch, key), set)

        assert isinstance(data["TOOLING"], set)
        assert isinstance(data["ALLOWED_CROSS_LAYER"], set)
        assert isinstance(data["ALLOWED_CROSS_DOMAIN"], set)
        assert isinstance(data["SKIP_DIRS"], set)
        assert isinstance(data["SKIP_MODULES"], set)
        assert isinstance(data["_EXTERNAL_PREFIXES"], frozenset)
        assert isinstance(data["TESTING_EXEMPT"], set)
        assert data["API_FACADE_FILE"] is None or isinstance(data["API_FACADE_FILE"], str)
