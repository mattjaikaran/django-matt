"""
Bundle size optimization analyzer.

Detects unused django-matt modules and provides recommendations
for reducing bundle size through tree-shaking and lazy loading.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


@dataclass
class ModuleInfo:
    """
    Information about a django-matt module.

    Attributes:
        name: Module name (e.g., "graphql", "billing").
        path: Path to the module.
        estimated_size_kb: Estimated size in kilobytes.
        is_used: Whether the module is imported anywhere.
        import_count: Number of times the module is imported.
        import_locations: Files that import this module.
        dependencies: Other modules this module depends on.
        is_core: Whether this is a core required module.
    """

    name: str
    path: Path
    estimated_size_kb: float = 0.0
    is_used: bool = False
    import_count: int = 0
    import_locations: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    is_core: bool = False


class BundleAnalysisResult(BaseModel):
    """
    Result of bundle size analysis.

    Attributes:
        total_size_kb: Total estimated size of all modules.
        core_size_kb: Size of core required modules.
        unused_size_kb: Size of unused modules.
        used_modules: List of modules in use.
        unused_modules: List of unused modules.
        recommendations: Optimization recommendations.
        import_time_ms: Time to import all modules in milliseconds.
    """

    total_size_kb: float = Field(..., description="Total estimated size")
    core_size_kb: float = Field(..., description="Core modules size")
    unused_size_kb: float = Field(0.0, description="Unused modules size")
    used_modules: list[str] = Field(default_factory=list)
    unused_modules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    import_time_ms: float = Field(0.0, description="Total import time")
    module_details: dict[str, dict] = Field(default_factory=dict)


class BundleAnalyzer:
    """
    Analyzer for django-matt bundle size and import optimization.

    Scans the project to detect which django-matt modules are actually
    used and provides recommendations for reducing bundle size.

    Example:
        >>> analyzer = BundleAnalyzer()
        >>> result = analyzer.analyze(Path("/path/to/project"))
        >>> for rec in result.recommendations:
        ...     print(rec)
    """

    # Core modules that are always required
    CORE_MODULES = {
        "api",
        "core",
        "conf",
    }

    # Module size estimates in KB (approximate)
    MODULE_SIZES: dict[str, float] = {
        "core": 45,
        "api": 20,
        "conf": 10,
        "auth": 85,
        "views": 35,
        "permissions": 25,
        "openapi": 40,
        "config": 15,
        "db": 30,
        "multitenancy": 65,
        "typegen": 45,
        "testing": 50,
        "utils": 25,
        "admin": 55,
        "billing": 95,
        "negotiation": 20,
        "websockets": 70,
        "flags": 40,
        "analytics": 80,
        "experiments": 75,
        "graphql": 180,
        "inspector": 35,
        "messaging": 90,
        "notifications": 85,
        "email": 55,
        "ai": 150,
        "ml": 220,
        "files": 45,
        "tasks": 60,
        "tasks_native": 75,
        "audits": 100,
        "audit": 40,
        "htmx": 35,
        "components": 65,
        "cli": 80,
        "deployment": 50,
        "observability": 55,
        "throttling": 25,
        "versioning": 30,
        "pagination": 20,
        "filtering": 35,
        "di": 40,
        "interceptors": 30,
        "streaming": 25,
        "events": 45,
        "exceptions": 20,
        "serialization": 25,
        "secrets": 35,
        "introspection": 30,
        "rpc": 55,
        "modules": 40,
        "cqrs": 50,
        "migration_tools": 60,
    }

    def __init__(self) -> None:
        """Initialize the bundle analyzer."""
        self._django_matt_path: Path | None = None
        self._modules: dict[str, ModuleInfo] = {}

    def analyze(
        self,
        project_path: Path | None = None,
        include_import_time: bool = True,
    ) -> BundleAnalysisResult:
        """
        Analyze bundle size and usage.

        Args:
            project_path: Path to the project to analyze.
            include_import_time: Whether to measure import times.

        Returns:
            BundleAnalysisResult with findings and recommendations.
        """
        project_path = project_path or Path.cwd()

        # Find django-matt installation
        self._find_django_matt()

        # Discover all modules
        self._discover_modules()

        # Scan project for imports
        self._scan_imports(project_path)

        # Measure import times if requested
        import_time_ms = 0.0
        if include_import_time:
            import_time_ms = self._measure_import_time()

        # Build result
        return self._build_result(import_time_ms)

    def _find_django_matt(self) -> None:
        """Find the django-matt package installation path."""
        spec = importlib.util.find_spec("django_matt")
        if spec and spec.origin:
            self._django_matt_path = Path(spec.origin).parent

    def _discover_modules(self) -> None:
        """Discover all available django-matt modules."""
        if not self._django_matt_path:
            return

        for item in self._django_matt_path.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                # Check if it's a Python package
                if (item / "__init__.py").exists():
                    module_name = item.name
                    self._modules[module_name] = ModuleInfo(
                        name=module_name,
                        path=item,
                        estimated_size_kb=self.MODULE_SIZES.get(module_name, 30),
                        is_core=module_name in self.CORE_MODULES,
                    )

    def _scan_imports(self, project_path: Path) -> None:
        """
        Scan project files for django-matt imports.

        Args:
            project_path: Path to the project.
        """
        for py_file in project_path.rglob("*.py"):
            # Skip django_matt's own files
            if "django_matt" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))
                self._extract_imports(tree, str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

    def _extract_imports(self, tree: ast.Module, file_path: str) -> None:
        """
        Extract django-matt imports from an AST.

        Args:
            tree: Parsed AST.
            file_path: Path to the source file.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import(alias.name, file_path)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._check_import(node.module, file_path)

    def _check_import(self, import_name: str, file_path: str) -> None:
        """
        Check if an import is from django-matt.

        Args:
            import_name: The imported module name.
            file_path: Path to the file containing the import.
        """
        if not import_name.startswith("django_matt"):
            return

        # Extract the module name (first level after django_matt)
        parts = import_name.split(".")
        if len(parts) >= 2:
            module_name = parts[1]
            if module_name in self._modules:
                module = self._modules[module_name]
                module.is_used = True
                module.import_count += 1
                if file_path not in module.import_locations:
                    module.import_locations.append(file_path)

    def _measure_import_time(self) -> float:
        """
        Measure total import time for all modules.

        Returns:
            Total import time in milliseconds.
        """
        total_time = 0.0

        for module_name in self._modules:
            full_name = f"django_matt.{module_name}"

            # Skip if already imported
            if full_name in sys.modules:
                continue

            start = time.perf_counter()
            try:
                importlib.import_module(full_name)
            except ImportError:
                pass
            total_time += (time.perf_counter() - start) * 1000

        return total_time

    def _build_result(self, import_time_ms: float) -> BundleAnalysisResult:
        """
        Build the analysis result.

        Args:
            import_time_ms: Measured import time.

        Returns:
            BundleAnalysisResult.
        """
        used_modules = []
        unused_modules = []
        total_size = 0.0
        core_size = 0.0
        unused_size = 0.0
        module_details = {}

        for module_name, module in self._modules.items():
            total_size += module.estimated_size_kb

            if module.is_core:
                core_size += module.estimated_size_kb
                used_modules.append(module_name)
            elif module.is_used:
                used_modules.append(module_name)
            else:
                unused_modules.append(module_name)
                unused_size += module.estimated_size_kb

            module_details[module_name] = {
                "size_kb": module.estimated_size_kb,
                "is_used": module.is_used,
                "import_count": module.import_count,
                "is_core": module.is_core,
            }

        # Generate recommendations
        recommendations = self._generate_recommendations(unused_modules, unused_size)

        return BundleAnalysisResult(
            total_size_kb=total_size,
            core_size_kb=core_size,
            unused_size_kb=unused_size,
            used_modules=sorted(used_modules),
            unused_modules=sorted(unused_modules),
            recommendations=recommendations,
            import_time_ms=import_time_ms,
            module_details=module_details,
        )

    def _generate_recommendations(self, unused_modules: list[str], unused_size: float) -> list[str]:
        """
        Generate optimization recommendations.

        Args:
            unused_modules: List of unused module names.
            unused_size: Total size of unused modules.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        if unused_size > 100:
            recommendations.append(
                f"Unused modules total ~{unused_size:.0f}KB. Consider using slim mode."
            )

        for module in unused_modules:
            size = self.MODULE_SIZES.get(module, 30)
            if size > 50:
                recommendations.append(
                    f"Remove '{module}' from INSTALLED_APPS or add to MATT_DISABLED_MODULES ({size}KB)"
                )

        # Large module suggestions
        large_unused = [m for m in unused_modules if self.MODULE_SIZES.get(m, 0) > 100]
        if large_unused:
            recommendations.append(
                f"Large unused modules: {', '.join(large_unused)}. "
                "These are good candidates for tree-shaking."
            )

        # Suggest slim mode config
        if len(unused_modules) > 5:
            recommendations.append(
                "Consider using MattAPI(mode='slim') for automatic module trimming"
            )

        return recommendations


def analyze_bundle(
    project_path: Path | str | None = None,
    include_import_time: bool = True,
) -> BundleAnalysisResult:
    """
    Analyze django-matt bundle size for a project.

    Args:
        project_path: Path to the project (defaults to current directory).
        include_import_time: Whether to measure import times.

    Returns:
        BundleAnalysisResult with findings and recommendations.

    Example:
        >>> result = analyze_bundle()
        >>> print(f"Total: {result.total_size_kb}KB")
        >>> print(f"Unused: {result.unused_size_kb}KB")
        >>> for rec in result.recommendations:
        ...     print(f"- {rec}")
    """
    path = Path(project_path) if project_path else None
    analyzer = BundleAnalyzer()
    return analyzer.analyze(path, include_import_time)


def generate_slim_config(project_path: Path | str | None = None) -> str:
    """
    Generate optimal SlimConfig based on project usage.

    Args:
        project_path: Path to the project.

    Returns:
        Python code string for SlimConfig.

    Example:
        >>> config_code = generate_slim_config()
        >>> print(config_code)
    """
    result = analyze_bundle(project_path, include_import_time=False)

    lines = [
        "from django_matt.slim import SlimConfig",
        "",
        "# Auto-generated slim configuration based on project analysis",
        "slim_config = SlimConfig(",
        f"    enabled_modules={result.used_modules!r},",
        f"    disabled_modules={result.unused_modules!r},",
        "    lazy_load=True,",
        ")",
    ]

    return "\n".join(lines)
