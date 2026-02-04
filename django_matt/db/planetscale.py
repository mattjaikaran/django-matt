"""
PlanetScale database support for Django Matt.

This module provides utilities for working with PlanetScale's serverless MySQL
platform, including connection configuration, branch-based workflow support,
and migration handling.

PlanetScale is a MySQL-compatible serverless database platform built on Vitess.
It offers features like:
- Non-blocking schema changes via deploy requests
- Git-like branching for database schemas
- Serverless connection pooling
- Global replication

Usage:
    from django_matt.db.planetscale import configure_planetscale, PlanetScaleBranch

    # Configure Django to use PlanetScale
    DATABASES = configure_planetscale()

    # Or with explicit connection string
    DATABASES = configure_planetscale(
        database_url="mysql://user:pass@host/db?ssl={'rejectUnauthorized':true}"
    )

    # Branch management
    branch = PlanetScaleBranch("my-feature-branch")
    if branch.exists():
        connection = branch.get_connection()
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, unquote, urlparse

from django.conf import settings
from django.db import connections

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper

logger = logging.getLogger(__name__)


# ==============================================================================
# Constants
# ==============================================================================

PLANETSCALE_HOSTS = [
    ".psdb.cloud",
    ".connect.psdb.cloud",
    "aws.connect.psdb.cloud",
    "gcp.connect.psdb.cloud",
]

DEFAULT_PLANETSCALE_PORT = 3306

# PlanetScale's CA certificate for SSL connections
# This is the DigiCert Global Root CA that PlanetScale uses
PLANETSCALE_CA_CERT = """-----BEGIN CERTIFICATE-----
MIIDrzCCApegAwIBAgIQCDvgVpBCRrGhdWrJWZHHSjANBgkqhkiG9w0BAQUFADBh
MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3
d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBD
QTAeFw0wNjExMTAwMDAwMDBaFw0zMTExMTAwMDAwMDBaMGExCzAJBgNVBAYTAlVT
MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j
b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IENBMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4jvhEXLeqKTTo1eqUKKPC3eQyaKl7hLOllsB
CSDMAZOnTjC3U/dDxGkAV53ijSLdhwZAAIEJzs4bg7/fzTtxRuLWZscFs3YnFo97
nh6Vfe63SKMI2tavegw5BmV/Sl0fvBf4q77uKNd0f3p4mVmFaG5cIzJLv07A6Fpt
43C/dxC//AH2hdmoRBBYMql1GNXRor5H4idq9Joz+EkIYIvUX7Q6hL+hqkpMfT7P
T19sdl6gSzeRntwi5m3OFBqOasv+zbMUZBfHWymeMr/y7vrTC0LUq7dBMtoM1O/4
gdW7jVg/tRvoSSiicNoxBN33shbyTApOB6jtSj1etX+jkMOvJwIDAQABo2MwYTAO
BgNVHQ8BAf8EBAMCAYYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUA95QNVbR
TLtm8KPiGxvDl7I90VUwHwYDVR0jBBgwFoAUA95QNVbRTLtm8KPiGxvDl7I90VUw
DQYJKoZIhvcNAQEFBQADggEBAMucN6pIExIK+t1EnE9SsPTfrgT1eXkIoyQY/Esr
hMAtudXH/vTBH1jLuG2cenTnmCmrEbXjcKChzUyImZOMkXDiqw8cvpOp/2PV5Adg
06O/nVsJ8dWO41P0jmP6P6fbtGbfYmbW0W5BjfIttep3Sp+dWOIrWcBAI+0tKIJF
PnlUkiaY4IBIqDfv8NZ5YBberOgOzW6sRBc4L0na4UU+Krk2U886UAb3LujEV0ls
YSEY1QSteDwsOoBrp+uvFRTp2InBuThs4pFsiv9kuXclVzDAGySj4dzp30d8tbQk
CAUw7C29C79Fv1C5qfPrmAESrciIxpg0X40KPMbp1ZWVbd4=
-----END CERTIFICATE-----"""


# ==============================================================================
# Exceptions
# ==============================================================================


class PlanetScaleError(Exception):
    """Base exception for PlanetScale operations."""


class PlanetScaleConnectionError(PlanetScaleError):
    """Error connecting to PlanetScale."""


class PlanetScaleBranchError(PlanetScaleError):
    """Error with PlanetScale branch operations."""


class PlanetScaleMigrationError(PlanetScaleError):
    """Error with PlanetScale migration operations."""


class PlanetScaleDDLError(PlanetScaleMigrationError):
    """Error when DDL operation is restricted on production branch."""


# ==============================================================================
# Connection String Parsing
# ==============================================================================


@dataclass
class PlanetScaleConnectionInfo:
    """Parsed PlanetScale connection information."""

    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_mode: str = "REQUIRED"
    ssl_ca: str | None = None
    branch: str | None = None
    is_production: bool = False
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_url(cls, url: str) -> PlanetScaleConnectionInfo:
        """
        Parse a PlanetScale connection URL.

        Supports formats:
        - mysql://user:pass@host/database
        - mysql://user:pass@host:port/database?ssl-mode=REQUIRED
        - DATABASE_URL format from PlanetScale dashboard

        Args:
            url: The connection URL to parse

        Returns:
            PlanetScaleConnectionInfo with parsed values
        """
        parsed = urlparse(url)

        # Extract basic components
        host = parsed.hostname or "localhost"
        port = parsed.port or DEFAULT_PLANETSCALE_PORT
        database = parsed.path.lstrip("/") if parsed.path else ""
        username = unquote(parsed.username or "")
        password = unquote(parsed.password or "")

        # Parse query parameters
        params = parse_qs(parsed.query)

        ssl_mode = "REQUIRED"
        if "ssl-mode" in params:
            ssl_mode = params["ssl-mode"][0].upper()
        elif "sslmode" in params:
            ssl_mode = params["sslmode"][0].upper()

        ssl_ca = params.get("ssl-ca", [None])[0]

        # Detect branch from host pattern (branch-name.region.psdb.cloud)
        branch = None
        host_parts = host.split(".")
        if len(host_parts) > 3 and any(h in host for h in PLANETSCALE_HOSTS):
            # First part might be branch identifier
            potential_branch = host_parts[0]
            if potential_branch not in ("aws", "gcp"):
                branch = potential_branch

        # Detect if this is likely a production branch
        is_production = cls._detect_production(host, database, branch, params)

        # Collect remaining options
        options = {}
        for key, values in params.items():
            if key not in ("ssl-mode", "sslmode", "ssl-ca"):
                options[key] = values[0] if len(values) == 1 else values

        return cls(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            ssl_mode=ssl_mode,
            ssl_ca=ssl_ca,
            branch=branch,
            is_production=is_production,
            options=options,
        )

    @staticmethod
    def _detect_production(host: str, database: str, branch: str | None, params: dict) -> bool:
        """Detect if connection is to a production branch."""
        # Check explicit production flag
        if params.get("production", ["false"])[0].lower() == "true":
            return True

        # Check branch name patterns
        if branch:
            branch_lower = branch.lower()
            if branch_lower in ("main", "master", "production", "prod"):
                return True

        # Check database name patterns
        db_lower = database.lower()
        if any(pattern in db_lower for pattern in ("prod", "production", "live", "-prd", "_prd")):
            return True

        return False

    def to_django_config(self) -> dict[str, Any]:
        """Convert to Django database configuration dictionary."""
        config = {
            "ENGINE": "django.db.backends.mysql",
            "NAME": self.database,
            "USER": self.username,
            "PASSWORD": self.password,
            "HOST": self.host,
            "PORT": str(self.port),
            "OPTIONS": {
                "charset": "utf8mb4",
                "ssl": self._get_ssl_options(),
            },
        }

        # Add any extra options
        for key, value in self.options.items():
            if key not in config["OPTIONS"]:
                config["OPTIONS"][key] = value

        return config

    def _get_ssl_options(self) -> dict[str, Any]:
        """Get SSL options for MySQL connection."""
        ssl_options: dict[str, Any] = {}

        if self.ssl_mode in ("REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"):
            # Use PlanetScale's CA cert if no custom CA provided
            if self.ssl_ca:
                ssl_options["ca"] = self.ssl_ca
            else:
                # Write CA cert to temp file for mysqlclient
                ssl_options["ca"] = _get_ca_cert_path()

            if self.ssl_mode == "VERIFY_IDENTITY":
                ssl_options["check_hostname"] = True

        return ssl_options


def _get_ca_cert_path() -> str:
    """
    Get path to PlanetScale CA certificate file.

    Creates a temporary file with the CA cert if needed.
    """
    # Check if user has set custom path
    custom_path = os.environ.get("PLANETSCALE_CA_CERT_PATH")
    if custom_path and Path(custom_path).exists():
        return custom_path

    # Create temp file with CA cert
    cert_hash = hashlib.md5(PLANETSCALE_CA_CERT.encode()).hexdigest()[:8]
    temp_dir = Path(tempfile.gettempdir())
    cert_path = temp_dir / f"planetscale_ca_{cert_hash}.pem"

    if not cert_path.exists():
        cert_path.write_text(PLANETSCALE_CA_CERT)

    return str(cert_path)


def parse_database_url(url: str) -> PlanetScaleConnectionInfo:
    """
    Parse a database URL into connection info.

    This is a convenience wrapper around PlanetScaleConnectionInfo.from_url().

    Args:
        url: Database connection URL

    Returns:
        PlanetScaleConnectionInfo object
    """
    return PlanetScaleConnectionInfo.from_url(url)


def is_planetscale_host(host: str) -> bool:
    """
    Check if a host is a PlanetScale host.

    Args:
        host: Hostname to check

    Returns:
        True if host is a PlanetScale host
    """
    return any(ps_host in host for ps_host in PLANETSCALE_HOSTS)


# ==============================================================================
# Branch Management
# ==============================================================================


@dataclass
class BranchInfo:
    """Information about a PlanetScale branch."""

    name: str
    database: str
    organization: str | None = None
    is_production: bool = False
    is_development: bool = False
    parent_branch: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schema_diff_available: bool = False
    ready: bool = True


class PlanetScaleBranch:
    """
    Manage PlanetScale database branches.

    PlanetScale uses Git-like branches for database schemas. This class
    provides utilities for connecting to specific branches and managing
    the branch workflow.

    Usage:
        # Connect to a feature branch
        branch = PlanetScaleBranch("my-feature")
        if branch.exists():
            with branch.get_connection() as conn:
                # Use connection
                pass

        # Check if we're on production
        main_branch = PlanetScaleBranch("main")
        if main_branch.is_production:
            print("Warning: Connected to production!")
    """

    def __init__(
        self,
        branch_name: str,
        database: str | None = None,
        organization: str | None = None,
    ):
        """
        Initialize branch manager.

        Args:
            branch_name: Name of the branch
            database: Database name (defaults to PLANETSCALE_DATABASE env var)
            organization: Organization name (defaults to PLANETSCALE_ORG env var)
        """
        self.branch_name = branch_name
        self.database = database or os.environ.get("PLANETSCALE_DATABASE", "")
        self.organization = organization or os.environ.get("PLANETSCALE_ORG", "")
        self._info: BranchInfo | None = None
        self._cli_available: bool | None = None

    @property
    def is_production(self) -> bool:
        """Check if this is a production branch."""
        if self._info:
            return self._info.is_production

        # Heuristic check based on name
        name_lower = self.branch_name.lower()
        return name_lower in ("main", "master", "production", "prod")

    @property
    def is_development(self) -> bool:
        """Check if this is a development branch."""
        return not self.is_production

    def _check_cli(self) -> bool:
        """Check if pscale CLI is available."""
        if self._cli_available is None:
            try:
                result = subprocess.run(
                    ["pscale", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._cli_available = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                self._cli_available = False
        return self._cli_available

    def exists(self) -> bool:
        """
        Check if the branch exists.

        Requires pscale CLI to be installed and authenticated.

        Returns:
            True if branch exists, False otherwise
        """
        if not self._check_cli():
            logger.warning("pscale CLI not available, cannot check branch existence")
            return True  # Assume exists

        try:
            result = subprocess.run(
                [
                    "pscale",
                    "branch",
                    "show",
                    self.branch_name,
                    "--database",
                    self.database,
                    "--org",
                    self.organization,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return True  # Assume exists on error

    def get_info(self, refresh: bool = False) -> BranchInfo | None:
        """
        Get detailed branch information.

        Requires pscale CLI.

        Args:
            refresh: Force refresh of cached info

        Returns:
            BranchInfo or None if not available
        """
        if self._info and not refresh:
            return self._info

        if not self._check_cli():
            return None

        try:
            result = subprocess.run(
                [
                    "pscale",
                    "branch",
                    "show",
                    self.branch_name,
                    "--database",
                    self.database,
                    "--org",
                    self.organization,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                self._info = BranchInfo(
                    name=data.get("name", self.branch_name),
                    database=data.get("database", self.database),
                    organization=data.get("organization", self.organization),
                    is_production=data.get("production", False),
                    is_development=not data.get("production", False),
                    parent_branch=data.get("parent_branch"),
                    ready=data.get("ready", True),
                )
                return self._info
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to get branch info: {e}")

        return None

    def get_connection_string(self) -> str | None:
        """
        Get connection string for this branch.

        Requires pscale CLI.

        Returns:
            Connection string or None
        """
        if not self._check_cli():
            return None

        try:
            result = subprocess.run(
                [
                    "pscale",
                    "password",
                    "create",
                    self.database,
                    self.branch_name,
                    f"django-matt-{self.branch_name}",
                    "--org",
                    self.organization,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                host = data.get("database_branch", {}).get("access_host_url", "")
                username = data.get("username", "")
                password = data.get("plain_text", "")
                database = self.database

                if host and username and password:
                    return f"mysql://{username}:{password}@{host}/{database}?ssl-mode=REQUIRED"
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to create connection string: {e}")

        return None

    def get_connection(self, alias: str = "default") -> BaseDatabaseWrapper:
        """
        Get a Django database connection for this branch.

        This requires the branch to already be configured in Django's
        DATABASES setting or uses the connection string from pscale CLI.

        Args:
            alias: Database alias to use

        Returns:
            Django database connection
        """
        # Check if alias is already configured for this branch
        if alias in settings.DATABASES:
            return connections[alias]

        # Try to get connection string via CLI
        conn_str = self.get_connection_string()
        if conn_str:
            info = PlanetScaleConnectionInfo.from_url(conn_str)
            config = info.to_django_config()

            # Create a new connection
            from django.db import ConnectionHandler

            handler = ConnectionHandler({alias: config})
            return handler[alias]

        raise PlanetScaleConnectionError(
            f"Cannot get connection for branch {self.branch_name}. "
            "Configure it in DATABASES or install pscale CLI."
        )


def get_branch_connection(
    branch_name: str,
    database: str | None = None,
    organization: str | None = None,
) -> BaseDatabaseWrapper:
    """
    Get a Django database connection for a specific PlanetScale branch.

    Convenience function that wraps PlanetScaleBranch.

    Args:
        branch_name: Name of the branch
        database: Database name
        organization: Organization name

    Returns:
        Django database connection
    """
    branch = PlanetScaleBranch(branch_name, database, organization)
    return branch.get_connection()


def detect_current_branch() -> str | None:
    """
    Detect the current PlanetScale branch from environment or settings.

    Checks:
    1. PLANETSCALE_BRANCH environment variable
    2. DATABASE_URL host pattern
    3. Django settings

    Returns:
        Branch name or None if not detected
    """
    # Check explicit env var
    branch = os.environ.get("PLANETSCALE_BRANCH")
    if branch:
        return branch

    # Check DATABASE_URL
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and is_planetscale_host(db_url):
        info = PlanetScaleConnectionInfo.from_url(db_url)
        if info.branch:
            return info.branch

    return None


def is_production_branch() -> bool:
    """
    Check if currently connected to a production branch.

    Returns:
        True if on production branch
    """
    branch_name = detect_current_branch()
    if branch_name:
        branch = PlanetScaleBranch(branch_name)
        return branch.is_production

    # Check environment
    env = os.environ.get("DJANGO_ENV", os.environ.get("ENVIRONMENT", "development"))
    return env.lower() in ("production", "prod")


# ==============================================================================
# Migration Handling
# ==============================================================================


# DDL statements that PlanetScale restricts on production branches
RESTRICTED_DDL_PATTERNS = [
    r"\bCREATE\s+TABLE\b",
    r"\bDROP\s+TABLE\b",
    r"\bALTER\s+TABLE\b",
    r"\bCREATE\s+INDEX\b",
    r"\bDROP\s+INDEX\b",
    r"\bTRUNCATE\b",
    r"\bRENAME\s+TABLE\b",
    r"\bCREATE\s+DATABASE\b",
    r"\bDROP\s+DATABASE\b",
]


def is_ddl_statement(sql: str) -> bool:
    """
    Check if a SQL statement is a DDL statement.

    Args:
        sql: SQL statement to check

    Returns:
        True if DDL statement
    """
    sql_upper = sql.upper().strip()
    for pattern in RESTRICTED_DDL_PATTERNS:
        if re.search(pattern, sql_upper):
            return True
    return False


class PlanetScaleMigrationRouter:
    """
    Database router that handles PlanetScale's DDL restrictions.

    PlanetScale's production branches have safe migrations enabled by default,
    which prevents direct DDL operations. This router helps manage migrations
    by routing DDL to development branches or raising warnings.

    Usage:
        # settings.py
        DATABASE_ROUTERS = ['django_matt.db.planetscale.PlanetScaleMigrationRouter']

        DATABASES = {
            'default': {  # Production branch
                ...
                'PLANETSCALE_PRODUCTION': True,
            },
            'development': {  # Development branch for migrations
                ...
                'PLANETSCALE_PRODUCTION': False,
            },
        }
    """

    def __init__(self):
        self.development_db = os.environ.get("PLANETSCALE_DEV_DB", "development")

    def db_for_read(self, model, **hints) -> str | None:
        """Route reads to default database."""
        return None  # Use default

    def db_for_write(self, model, **hints) -> str | None:
        """Route writes to default database."""
        return None  # Use default

    def allow_relation(self, obj1, obj2, **hints) -> bool | None:
        """Allow relations between objects."""
        return None  # Use default

    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints
    ) -> bool | None:
        """
        Control which database migrations run on.

        For production PlanetScale branches, migrations should be applied
        via deploy requests, not directly.
        """
        # Check if this is a PlanetScale production database
        if db in settings.DATABASES:
            db_settings = settings.DATABASES[db]
            is_ps_production = db_settings.get("PLANETSCALE_PRODUCTION", False)

            if is_ps_production:
                # Check if there's a development database available
                if self.development_db in settings.DATABASES:
                    # Redirect to development
                    logger.info(
                        f"Redirecting migration for {app_label}.{model_name} "
                        f"from production to {self.development_db}"
                    )
                    return db == self.development_db
                # Log warning but allow (user may be using deploy requests)
                logger.warning(
                    f"Migration for {app_label}.{model_name} targeting "
                    f"PlanetScale production branch. Use deploy requests "
                    f"for safe schema changes."
                )

        return None  # Use default behavior


@dataclass
class SchemaDiff:
    """Represents a schema difference between branches."""

    table: str
    change_type: str  # 'create', 'drop', 'alter'
    sql: str
    description: str


@dataclass
class DeployRequestInfo:
    """Information about a PlanetScale deploy request."""

    id: str
    number: int
    branch: str
    into_branch: str
    state: str  # 'open', 'approved', 'deployed', 'closed'
    deployment_state: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None
    approved: bool = False
    deployable: bool = False
    has_schema_changes: bool = False


class PlanetScaleDeployWorkflow:
    """
    Manage PlanetScale deploy request workflow.

    Deploy requests are PlanetScale's mechanism for safe schema changes.
    Instead of running DDL directly on production, you:
    1. Make changes on a development branch
    2. Create a deploy request to merge to production
    3. Review the schema diff
    4. Deploy (apply changes with zero downtime)

    Usage:
        workflow = PlanetScaleDeployWorkflow("my-feature", "main")

        # Get schema diff
        diff = workflow.get_schema_diff()
        for change in diff:
            print(f"{change.change_type} {change.table}: {change.description}")

        # Create deploy request
        dr = workflow.create_deploy_request()
        print(f"Created deploy request #{dr.number}")

        # Deploy
        workflow.deploy(dr.number)
    """

    def __init__(
        self,
        source_branch: str,
        target_branch: str = "main",
        database: str | None = None,
        organization: str | None = None,
    ):
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.database = database or os.environ.get("PLANETSCALE_DATABASE", "")
        self.organization = organization or os.environ.get("PLANETSCALE_ORG", "")
        self._cli_available: bool | None = None

    def _check_cli(self) -> bool:
        """Check if pscale CLI is available."""
        if self._cli_available is None:
            try:
                result = subprocess.run(
                    ["pscale", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._cli_available = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                self._cli_available = False
        return self._cli_available

    def _run_pscale(self, *args: str, timeout: int = 60) -> dict | None:
        """Run pscale command and return JSON output."""
        if not self._check_cli():
            raise PlanetScaleError("pscale CLI is not available")

        cmd = ["pscale", *args, "--format", "json"]
        if self.database:
            cmd.extend(["--database", self.database])
        if self.organization:
            cmd.extend(["--org", self.organization])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return json.loads(result.stdout) if result.stdout.strip() else {}
            logger.error(f"pscale command failed: {result.stderr}")
            return None
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.error(f"pscale command error: {e}")
            return None

    def get_schema_diff(self) -> list[SchemaDiff]:
        """
        Get schema differences between source and target branches.

        Returns:
            List of SchemaDiff objects
        """
        result = self._run_pscale(
            "deploy-request",
            "diff",
            self.source_branch,
            self.target_branch,
        )

        if not result:
            return []

        diffs = []
        for item in result.get("schema_diff", []):
            diffs.append(
                SchemaDiff(
                    table=item.get("table_name", ""),
                    change_type=item.get("change_type", ""),
                    sql=item.get("sql", ""),
                    description=item.get("description", ""),
                )
            )

        return diffs

    def create_deploy_request(self, notes: str = "") -> DeployRequestInfo | None:
        """
        Create a deploy request from source to target branch.

        Args:
            notes: Optional notes for the deploy request

        Returns:
            DeployRequestInfo or None on failure
        """
        args = ["deploy-request", "create", self.source_branch]
        if notes:
            args.extend(["--notes", notes])

        result = self._run_pscale(*args)

        if result:
            return DeployRequestInfo(
                id=result.get("id", ""),
                number=result.get("number", 0),
                branch=result.get("branch", self.source_branch),
                into_branch=result.get("into_branch", self.target_branch),
                state=result.get("state", "open"),
                deployment_state=result.get("deployment_state"),
                approved=result.get("approved", False),
                deployable=result.get("deployable", False),
                has_schema_changes=result.get("has_schema_changes", False),
            )

        return None

    def get_deploy_request(self, number: int) -> DeployRequestInfo | None:
        """
        Get information about a deploy request.

        Args:
            number: Deploy request number

        Returns:
            DeployRequestInfo or None
        """
        result = self._run_pscale("deploy-request", "show", str(number))

        if result:
            return DeployRequestInfo(
                id=result.get("id", ""),
                number=result.get("number", number),
                branch=result.get("branch", ""),
                into_branch=result.get("into_branch", ""),
                state=result.get("state", ""),
                deployment_state=result.get("deployment_state"),
                approved=result.get("approved", False),
                deployable=result.get("deployable", False),
                has_schema_changes=result.get("has_schema_changes", False),
            )

        return None

    def deploy(self, number: int, wait: bool = True, timeout: int = 300) -> bool:
        """
        Execute a deploy request.

        Args:
            number: Deploy request number
            wait: Wait for deployment to complete
            timeout: Timeout in seconds when waiting

        Returns:
            True if deployment successful
        """
        args = ["deploy-request", "deploy", str(number)]
        if wait:
            args.append("--wait")

        result = self._run_pscale(*args, timeout=timeout)
        return result is not None


def safe_migrate(
    source_branch: str | None = None,
    target_branch: str = "main",
    database: str | None = None,
    organization: str | None = None,
    auto_deploy: bool = False,
) -> DeployRequestInfo | None:
    """
    Run Django migrations safely using PlanetScale deploy requests.

    This function:
    1. Runs migrations on a development branch
    2. Creates a deploy request to merge schema changes
    3. Optionally auto-deploys

    Args:
        source_branch: Development branch (defaults to current branch)
        target_branch: Production branch to deploy to
        database: PlanetScale database name
        organization: PlanetScale organization
        auto_deploy: Automatically deploy after creating request

    Returns:
        DeployRequestInfo if deploy request created, None otherwise
    """
    # Determine source branch
    if not source_branch:
        source_branch = detect_current_branch()
        if not source_branch:
            raise PlanetScaleMigrationError(
                "Cannot determine source branch. Set PLANETSCALE_BRANCH or pass source_branch."
            )

    # Check we're not trying to migrate production directly
    source = PlanetScaleBranch(source_branch, database, organization)
    if source.is_production:
        raise PlanetScaleDDLError(
            f"Cannot run migrations directly on production branch '{source_branch}'. "
            f"Use a development branch and deploy requests."
        )

    # Run Django migrations on the development branch
    # This assumes the DATABASE is configured for the dev branch
    from django.core.management import call_command

    logger.info(f"Running migrations on branch '{source_branch}'...")
    call_command("migrate", "--verbosity=1")

    # Create deploy request
    workflow = PlanetScaleDeployWorkflow(source_branch, target_branch, database, organization)

    # Check for schema changes
    diff = workflow.get_schema_diff()
    if not diff:
        logger.info("No schema changes to deploy.")
        return None

    logger.info(f"Found {len(diff)} schema changes:")
    for change in diff:
        logger.info(f"  {change.change_type} {change.table}")

    # Create deploy request
    dr = workflow.create_deploy_request(notes="Django migrations via django-matt")
    if not dr:
        raise PlanetScaleMigrationError("Failed to create deploy request")

    logger.info(f"Created deploy request #{dr.number}")

    # Auto-deploy if requested
    if auto_deploy and dr.deployable:
        logger.info("Auto-deploying...")
        success = workflow.deploy(dr.number)
        if success:
            logger.info("Deployment successful!")
        else:
            logger.warning("Deployment may have failed. Check PlanetScale dashboard.")

    return dr


# ==============================================================================
# Django Configuration
# ==============================================================================


def configure_planetscale(
    database_url: str | None = None,
    branch: str | None = None,
    conn_max_age: int | None = 0,
    conn_health_checks: bool = True,
    options: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Configure Django DATABASES for PlanetScale.

    This function returns a DATABASES configuration dict for use in settings.py.
    It handles:
    - Connection string parsing from DATABASE_URL
    - SSL certificate configuration
    - Serverless-optimized connection pooling
    - Branch detection

    Args:
        database_url: PlanetScale connection URL (defaults to DATABASE_URL env var)
        branch: Branch name (for documentation, auto-detected from URL if not set)
        conn_max_age: Connection max age (0 for serverless, None for persistent)
        conn_health_checks: Enable connection health checks
        options: Additional MySQL options

    Returns:
        DATABASES configuration dict

    Example:
        # settings.py
        from django_matt.db.planetscale import configure_planetscale

        DATABASES = configure_planetscale()

        # Or with explicit URL
        DATABASES = configure_planetscale(
            database_url="mysql://user:pass@host/db?ssl-mode=REQUIRED"
        )
    """
    # Get connection URL
    url = database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        raise PlanetScaleConnectionError(
            "No database URL provided. Set DATABASE_URL or pass database_url parameter."
        )

    # Parse URL
    info = PlanetScaleConnectionInfo.from_url(url)

    # Get Django config
    config = info.to_django_config()

    # Add connection pooling settings
    # For serverless, conn_max_age=0 is recommended to avoid stale connections
    config["CONN_MAX_AGE"] = conn_max_age

    # Add health checks (Django 5.1+)
    config["CONN_HEALTH_CHECKS"] = conn_health_checks

    # Add custom options
    if options:
        config["OPTIONS"].update(options)

    # Add PlanetScale metadata
    config["PLANETSCALE_BRANCH"] = branch or info.branch
    config["PLANETSCALE_PRODUCTION"] = info.is_production

    return {"default": config}


def get_planetscale_config(alias: str = "default") -> dict[str, Any] | None:
    """
    Get PlanetScale-specific configuration from Django settings.

    Args:
        alias: Database alias

    Returns:
        PlanetScale config dict or None if not PlanetScale
    """
    if alias not in settings.DATABASES:
        return None

    db_config = settings.DATABASES[alias]

    # Check if this looks like a PlanetScale database
    host = db_config.get("HOST", "")
    if not is_planetscale_host(host):
        return None

    return {
        "host": host,
        "database": db_config.get("NAME"),
        "branch": db_config.get("PLANETSCALE_BRANCH"),
        "is_production": db_config.get("PLANETSCALE_PRODUCTION", False),
    }


# ==============================================================================
# Health Check
# ==============================================================================


def check_planetscale_connection(alias: str = "default") -> dict[str, Any]:
    """
    Check PlanetScale database connection health.

    Returns:
        Dict with connection status and details
    """
    result = {
        "healthy": False,
        "database": alias,
        "host": None,
        "latency_ms": None,
        "ssl_enabled": None,
        "branch": None,
        "is_production": None,
        "error": None,
    }

    try:
        conn = connections[alias]

        # Get config
        config = settings.DATABASES.get(alias, {})
        result["host"] = config.get("HOST")
        result["branch"] = config.get("PLANETSCALE_BRANCH")
        result["is_production"] = config.get("PLANETSCALE_PRODUCTION")

        # Test connection with timing
        import time

        start = time.perf_counter()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        end = time.perf_counter()

        result["latency_ms"] = round((end - start) * 1000, 2)

        # Check SSL status
        with conn.cursor() as cursor:
            cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
            row = cursor.fetchone()
            result["ssl_enabled"] = bool(row and row[1])

        result["healthy"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


async def acheck_planetscale_connection(alias: str = "default") -> dict[str, Any]:
    """
    Async version of check_planetscale_connection.

    Returns:
        Dict with connection status and details
    """
    import asyncio

    # Run sync version in thread pool
    return await asyncio.to_thread(check_planetscale_connection, alias)


# ==============================================================================
# Exports
# ==============================================================================

__all__ = [
    # Exceptions
    "PlanetScaleError",
    "PlanetScaleConnectionError",
    "PlanetScaleBranchError",
    "PlanetScaleMigrationError",
    "PlanetScaleDDLError",
    # Connection parsing
    "PlanetScaleConnectionInfo",
    "parse_database_url",
    "is_planetscale_host",
    # Branch management
    "BranchInfo",
    "PlanetScaleBranch",
    "get_branch_connection",
    "detect_current_branch",
    "is_production_branch",
    # Migration handling
    "PlanetScaleMigrationRouter",
    "PlanetScaleDeployWorkflow",
    "SchemaDiff",
    "DeployRequestInfo",
    "is_ddl_statement",
    "safe_migrate",
    # Configuration
    "configure_planetscale",
    "get_planetscale_config",
    # Health check
    "check_planetscale_connection",
    "acheck_planetscale_connection",
]
