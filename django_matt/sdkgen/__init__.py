"""
Django Matt SDK Generation - Produce ready-to-publish client libraries from API definitions.

Generates complete, typed client SDKs for TypeScript (npm), Python (PyPI), and Swift (SPM)
from OpenAPI schemas extracted from django_matt API routes and controllers.

Example:
    from django_matt.sdkgen import TypeScriptSDKGenerator, PythonSDKGenerator, SDKConfig

    config = SDKConfig(
        package_name="my-api-client",
        version="1.0.0",
        base_url="https://api.example.com",
        auth_type="jwt",
        output_dir=Path("./sdk/ts"),
    )

    generator = TypeScriptSDKGenerator()
    output = generator.generate(openapi_schema, config)
    output.write_to_disk()
"""

from django_matt.sdkgen.base import SchemaVersioning, SDKConfig, SDKGenerator, SDKOutput
from django_matt.sdkgen.python_sdk import PythonSDKGenerator
from django_matt.sdkgen.swift import SwiftSDKGenerator
from django_matt.sdkgen.typescript import TypeScriptSDKGenerator

__all__ = [
    "SDKConfig",
    "SDKGenerator",
    "SDKOutput",
    "SchemaVersioning",
    "TypeScriptSDKGenerator",
    "PythonSDKGenerator",
    "SwiftSDKGenerator",
]
