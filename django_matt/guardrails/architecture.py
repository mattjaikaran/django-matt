"""
TOML-based architecture contract parser and rule model.

Parses ``.matt/architecture.toml`` into a structured
``ArchitectureContract`` dataclass, validates the contract for internal
consistency, and converts it to the dictionary format used by
``scripts/check_architecture.py`` module-level variables.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Known rule codes valid in ci.fail_on ──────────────────────────────────────

_KNOWN_RULES: frozenset[str] = frozenset(
    {"LAYER-DEP", "CROSS-DOMAIN", "NO-TEST-IMPORT"}
)

# ── Contract data model ───────────────────────────────────────────────────────


@dataclass
class ArchitectureContract:
    """Parsed architecture contract from .matt/architecture.toml.

    Attributes:
        layers: Mapping of layer name → list of module names.
            Order is significant: first key is lowest layer.
        layer_order: Layer names in bottom-up order (L0, L1, L2, L3).
        exempt_modules: Tooling / support modules exempt from all checks.
        cross_layer_exemptions: (source_module, target_module) pairs
            exempt from LAYER-DEP violations.
        cross_domain_exemptions: (source_module, target_module) pairs
            exempt from CROSS-DOMAIN violations.
        external_prefixes: Package prefixes that are never django-matt
            modules (e.g. "django.", "pydantic.").
        skip_dirs: Directory names to skip when collecting files.
        skip_modules: Module names to skip entirely.
        test_exempt_modules: Modules exempt from all checks (import from
            anywhere allowed).
        api_facade_file: Path to the API facade file that imports from
            anywhere, or ``None``.
        ci_fail_on: Rule codes that block CI on violation.
    """

    layers: dict[str, list[str]] = field(default_factory=dict)
    layer_order: list[str] = field(default_factory=list)
    exempt_modules: set[str] = field(default_factory=set)
    cross_layer_exemptions: set[tuple[str, str]] = field(default_factory=set)
    cross_domain_exemptions: set[tuple[str, str]] = field(default_factory=set)
    external_prefixes: frozenset[str] = field(default_factory=frozenset)
    skip_dirs: set[str] = field(default_factory=set)
    skip_modules: set[str] = field(default_factory=set)
    test_exempt_modules: set[str] = field(default_factory=set)
    api_facade_file: str | None = None
    ci_fail_on: set[str] = field(default_factory=set)


# ── Default contract (used when no TOML file found) ──────────────────────────

DEFAULT_CONTRACT = ArchitectureContract()


# ── TOML parsing ──────────────────────────────────────────────────────────────


def load_contract(path: str | Path) -> ArchitectureContract:
    """Parse ``.matt/architecture.toml`` into an ArchitectureContract.

    Args:
        path: Filesystem path to the TOML file.

    Returns:
        A populated ``ArchitectureContract``.  If the file does not exist
        or cannot be parsed, returns ``DEFAULT_CONTRACT``.
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return DEFAULT_CONTRACT

    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        return DEFAULT_CONTRACT

    return _parse_contract(data)


def _parse_contract(data: dict[str, Any]) -> ArchitectureContract:
    """Build ArchitectureContract from parsed TOML dict."""
    contract = ArchitectureContract()

    # ── Layers ────────────────────────────────────────────────────────────────
    layers_raw: dict[str, list[str]] = data.get("layers", {})  # type: ignore[assignment]
    if isinstance(layers_raw, dict):
        contract.layers = {
            k: [str(m) for m in v] if isinstance(v, list) else []
            for k, v in layers_raw.items()
            if isinstance(k, str)
        }
        contract.layer_order = list(contract.layers.keys())

    # ── Tooling / exempt modules ──────────────────────────────────────────────
    tooling = data.get("tooling")
    if isinstance(tooling, dict):
        tmods = tooling.get("modules")
        if isinstance(tmods, list):
            contract.exempt_modules = {str(m) for m in tmods}

    # ── Exemptions table ──────────────────────────────────────────────────────
    exemptions = data.get("exemptions")
    if isinstance(exemptions, dict):
        te = exemptions.get("testing_exempt")
        if isinstance(te, list):
            contract.test_exempt_modules = {str(m) for m in te}
        aff = exemptions.get("api_facade_file")
        if isinstance(aff, str) and aff.strip():
            contract.api_facade_file = aff.strip()

    # ── Rules: cross-layer / cross-domain ─────────────────────────────────────
    rules = data.get("rules")
    if isinstance(rules, dict):
        cl = rules.get("cross_layer")
        if isinstance(cl, list):
            contract.cross_layer_exemptions = {
                (str(item["source"]), str(item["target"]))
                for item in cl
                if isinstance(item, dict) and "source" in item and "target" in item
            }
        cd = rules.get("cross_domain")
        if isinstance(cd, list):
            contract.cross_domain_exemptions = {
                (str(item["source"]), str(item["target"]))
                for item in cd
                if isinstance(item, dict) and "source" in item and "target" in item
            }

    # ── External prefixes ─────────────────────────────────────────────────────
    ext = data.get("external")
    if isinstance(ext, dict):
        prefixes = ext.get("prefixes")
        if isinstance(prefixes, list):
            contract.external_prefixes = frozenset(str(p) for p in prefixes)

    # ── Skip config ───────────────────────────────────────────────────────────
    skip = data.get("skip")
    if isinstance(skip, dict):
        dirs = skip.get("directories")
        if isinstance(dirs, list):
            contract.skip_dirs = {str(d) for d in dirs}
        mods = skip.get("modules")
        if isinstance(mods, list):
            contract.skip_modules = {str(m) for m in mods}

    # ── CI config ─────────────────────────────────────────────────────────────
    ci = data.get("ci")
    if isinstance(ci, dict):
        fo = ci.get("fail_on")
        if isinstance(fo, list):
            contract.ci_fail_on = {str(r) for r in fo}

    return contract


# ── Validation ────────────────────────────────────────────────────────────────


def validate_contract(contract: ArchitectureContract) -> list[str]:
    """Validate an ArchitectureContract for internal consistency.

    Args:
        contract: The contract to validate.

    Returns:
        A list of human-readable error strings.  An empty list means the
        contract is valid.
    """
    errors: list[str] = []

    # ── Layers sanity ─────────────────────────────────────────────────────────
    all_layered: set[str] = set()
    seen_modules: dict[str, str] = {}  # module → layer name

    for name, modules in contract.layers.items():
        for m in modules:
            if m in seen_modules:
                errors.append(
                    f"Module '{m}' appears in both '{seen_modules[m]}' "
                    f"and '{name}' layers"
                )
            else:
                seen_modules[m] = name
            all_layered.add(m)

    if contract.layers and not contract.layer_order:
        errors.append("layers present but layer_order is empty")

    # ── Exempt / layered overlap ──────────────────────────────────────────────
    overlap = contract.exempt_modules & all_layered
    if overlap:
        errors.append(
            f"Exempt modules also appear in layers: {sorted(overlap)}"
        )

    # ── Cross-layer exemptions must reference real modules ────────────────────
    all_known = all_layered | contract.exempt_modules | contract.test_exempt_modules
    known_without_test_exempt = all_layered | contract.exempt_modules
    for src, tgt in contract.cross_layer_exemptions:
        if src not in all_known:
            errors.append(
                f"cross_layer_exemption source '{src}' is not a known module"
            )
        if tgt not in all_known:
            errors.append(
                f"cross_layer_exemption target '{tgt}' is not a known module"
            )

    # ── Cross-domain exemptions must reference domain modules ─────────────────
    domain_mods: set[str] = set(contract.layers.get("domain", []))
    for src, tgt in contract.cross_domain_exemptions:
        if src not in domain_mods:
            errors.append(
                f"cross_domain_exemption source '{src}' is not a domain module"
            )
        if tgt not in domain_mods:
            errors.append(
                f"cross_domain_exemption target '{tgt}' is not a domain module"
            )

    # ── Test-exempt modules must be known ─────────────────────────────────────
    for m in contract.test_exempt_modules:
        if m not in known_without_test_exempt:
            errors.append(
                f"test_exempt module '{m}' is not a known module"
            )

    # ── CI rule codes ─────────────────────────────────────────────────────────
    for rule in contract.ci_fail_on:
        if rule not in _KNOWN_RULES:
            errors.append(
                f"Unknown CI rule '{rule}'; known rules: "
                f"{sorted(_KNOWN_RULES)}"
            )

    # ── API facade file ───────────────────────────────────────────────────────
    if contract.api_facade_file is not None:
        # Must be a string that looks like a file path
        aff = contract.api_facade_file
        if not aff.endswith(".py"):
            errors.append(
                f"api_facade_file '{aff}' does not end with .py"
            )
        if ".." in aff:
            errors.append(
                f"api_facade_file '{aff}' contains parent traversal"
            )

    return errors


# ── Checker data conversion ───────────────────────────────────────────────────


def contract_to_checker_data(contract: ArchitectureContract) -> dict[str, Any]:
    """Convert a contract to the flat dict form used by check_architecture.py.

    The returned dictionary has keys matching the module-level variables of
    ``scripts/check_architecture.py`` so that the checker can consume
    contracts transparently:

    - ``FOUNDATION``, ``INFRASTRUCTURE``, ``DOMAIN``, ``INTERFACE``: sets
      of module names per layer.
    - ``TOOLING``: set of exempt/tooling module names.
    - ``ALLOWED_CROSS_LAYER``: set of (source, target) tuples.
    - ``ALLOWED_CROSS_DOMAIN``: set of (source, target) tuples.
    - ``SKIP_DIRS``, ``SKIP_MODULES``: sets of names to skip.
    - ``_EXTERNAL_PREFIXES``: frozenset of known-external prefixes.
    - ``TESTING_EXEMPT``: set of modules exempt from all checks.
    - ``API_FACADE_FILE``: str or None.

    Args:
        contract: A (possibly validated) ArchitectureContract.

    Returns:
        Dictionary suitable for feeding into ``scripts/check_architecture.py``
        as overrides.
    """
    return {
        "FOUNDATION": set(contract.layers.get("foundation", [])),
        "INFRASTRUCTURE": set(contract.layers.get("infrastructure", [])),
        "DOMAIN": set(contract.layers.get("domain", [])),
        "INTERFACE": set(contract.layers.get("interface", [])),
        "TOOLING": contract.exempt_modules,
        "ALLOWED_CROSS_LAYER": contract.cross_layer_exemptions,
        "ALLOWED_CROSS_DOMAIN": contract.cross_domain_exemptions,
        "SKIP_DIRS": contract.skip_dirs,
        "SKIP_MODULES": contract.skip_modules,
        "_EXTERNAL_PREFIXES": contract.external_prefixes,
        "TESTING_EXEMPT": contract.test_exempt_modules,
        "API_FACADE_FILE": contract.api_facade_file,
    }
