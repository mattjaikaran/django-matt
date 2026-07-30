"""
Architecture guardrails — declarative contracts as code, plus
schema-to-test generation.

Provides loading, validation, and conversion of architecture contracts
defined in TOML format (``.matt/architecture.toml``). Also includes
``SchemaTestGenerator`` and ``SmartTestGenerator`` for generating
edge-case validation tests from Pydantic schemas.

Example:
    >>> from django_matt.guardrails import load_contract, ArchitectureContract
    >>> contract = load_contract(".matt/architecture.toml")
    >>> errors = validate_contract(contract)
    >>> if errors:
    ...     for e in errors:
    ...         print(e)
"""

from django_matt.guardrails.architecture import (
    DEFAULT_CONTRACT,
    ArchitectureContract,
    contract_to_checker_data,
    load_contract,
    validate_contract,
)

from django_matt.guardrails.testgen import (
    SchemaTestGenerator,
    generate_test_file,
    generate_tests,
)

from django_matt.guardrails.testgen_smart import (
    SmartTestGenerator,
    generate_smart_tests,
)

__all__ = [
    "ArchitectureContract",
    "DEFAULT_CONTRACT",
    "SchemaTestGenerator",
    "SmartTestGenerator",
    "contract_to_checker_data",
    "generate_smart_tests",
    "generate_test_file",
    "generate_tests",
    "load_contract",
    "validate_contract",
]
