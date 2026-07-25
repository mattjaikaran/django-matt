"""Tests for starter templates system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from django_matt.cli.templates.starters import (
    STARTERS_DIR,
    TEMPLATE_NAMES,
    get_template_dir,
    list_templates,
    load_metadata,
    render_template,
)

REQUIRED_METADATA_KEYS = {"name", "description", "modules", "features"}
REQUIRED_PROJECT_FILES = {
    "manage.py",
    "config/settings.py",
    "config/urls.py",
    "config/asgi.py",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    "README.md",
}


class TestMetadata:
    """Test metadata.json for each template."""

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_metadata_exists(self, name: str) -> None:
        template_dir = STARTERS_DIR / name
        metadata_path = template_dir / "metadata.json"
        assert metadata_path.exists(), f"metadata.json missing for {name}"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_metadata_valid_json(self, name: str) -> None:
        metadata = load_metadata(name)
        assert isinstance(metadata, dict)

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_metadata_has_required_keys(self, name: str) -> None:
        metadata = load_metadata(name)
        missing = REQUIRED_METADATA_KEYS - set(metadata.keys())
        assert not missing, f"metadata.json for {name} missing keys: {missing}"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_metadata_name_matches_directory(self, name: str) -> None:
        metadata = load_metadata(name)
        assert metadata["name"] == name

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_metadata_modules_is_list(self, name: str) -> None:
        metadata = load_metadata(name)
        assert isinstance(metadata["modules"], list)
        assert len(metadata["modules"]) > 0

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_metadata_features_is_list(self, name: str) -> None:
        metadata = load_metadata(name)
        assert isinstance(metadata["features"], list)
        assert len(metadata["features"]) > 0


class TestTemplateStructure:
    """Test that each template has the required project files."""

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_project_template_dir_exists(self, name: str) -> None:
        template_dir = STARTERS_DIR / name / "project_template"
        assert template_dir.exists(), f"project_template/ missing for {name}"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_required_files_exist(self, name: str) -> None:
        template_dir = STARTERS_DIR / name / "project_template"
        for rel_path in REQUIRED_PROJECT_FILES:
            full_path = template_dir / rel_path
            # app files use "app/" dir in template
            assert full_path.exists(), f"{rel_path} missing in {name} template"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_app_dir_exists(self, name: str) -> None:
        template_dir = STARTERS_DIR / name / "project_template"
        app_dir = template_dir / "app"
        assert app_dir.exists(), f"app/ directory missing in {name} template"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_app_has_models(self, name: str) -> None:
        models_path = STARTERS_DIR / name / "project_template" / "app" / "models.py"
        assert models_path.exists(), f"app/models.py missing in {name} template"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_app_has_controllers(self, name: str) -> None:
        controllers_path = STARTERS_DIR / name / "project_template" / "app" / "controllers.py"
        assert controllers_path.exists(), f"app/controllers.py missing in {name}"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_app_has_schemas(self, name: str) -> None:
        schemas_path = STARTERS_DIR / name / "project_template" / "app" / "schemas.py"
        assert schemas_path.exists(), f"app/schemas.py missing in {name} template"


class TestTemplateVariableSubstitution:
    """Test that {{ project_name }} placeholders are replaced correctly."""

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_render_replaces_project_name(self, name: str, tmp_path: Path) -> None:
        project_name = "testproject"
        output = render_template(name, project_name, tmp_path / project_name)

        settings = output / "config" / "settings.py"
        assert settings.exists()
        content = settings.read_text()
        assert "{{ project_name }}" not in content
        assert project_name in content

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_render_replaces_in_pyproject(self, name: str, tmp_path: Path) -> None:
        project_name = "myapp"
        output = render_template(name, project_name, tmp_path / project_name)

        pyproject = output / "pyproject.toml"
        content = pyproject.read_text()
        assert "{{ project_name }}" not in content
        assert f'name = "{project_name}"' in content

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_render_replaces_in_docker_compose(self, name: str, tmp_path: Path) -> None:
        project_name = "dockerapp"
        output = render_template(name, project_name, tmp_path / project_name)

        compose = output / "docker-compose.yml"
        content = compose.read_text()
        assert "{{ project_name }}" not in content
        assert project_name in content

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_render_renames_app_directory(self, name: str, tmp_path: Path) -> None:
        project_name = "renamed"
        output = render_template(name, project_name, tmp_path / project_name)

        app_dir = output / f"{project_name}_app"
        assert app_dir.exists(), f"Expected {project_name}_app/ directory"
        assert not (output / "app").exists(), "Template app/ dir should be renamed"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_render_app_config_uses_project_name(self, name: str, tmp_path: Path) -> None:
        project_name = "configtest"
        output = render_template(name, project_name, tmp_path / project_name)

        apps_py = output / f"{project_name}_app" / "apps.py"
        content = apps_py.read_text()
        assert f'name = "{project_name}_app"' in content

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_no_leftover_placeholders(self, name: str, tmp_path: Path) -> None:
        project_name = "cleanproject"
        output = render_template(name, project_name, tmp_path / project_name)

        text_extensions = {".py", ".toml", ".yml", ".yaml", ".json", ".md"}
        for path in output.rglob("*"):
            if path.is_file() and path.suffix in text_extensions:
                content = path.read_text()
                assert "{{ project_name }}" not in content, (
                    f"Unreplaced placeholder in {path.relative_to(output)}"
                )


class TestListTemplates:
    """Test template listing functionality."""

    def test_list_templates_returns_all(self) -> None:
        templates = list_templates()
        names = {t["name"] for t in templates}
        assert names == set(TEMPLATE_NAMES)

    def test_list_templates_has_descriptions(self) -> None:
        templates = list_templates()
        for tmpl in templates:
            assert tmpl["description"], f"{tmpl['name']} has empty description"

    def test_list_templates_returns_dicts(self) -> None:
        templates = list_templates()
        assert all(isinstance(t, dict) for t in templates)


class TestGetTemplateDir:
    """Test template directory resolution."""

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_valid_template_name(self, name: str) -> None:
        result = get_template_dir(name)
        assert result.exists()
        assert result.is_dir()

    def test_invalid_template_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown template"):
            get_template_dir("nonexistent")

    def test_alias_starter_resolves(self) -> None:
        result = get_template_dir("starter")
        assert result.name == "api-only"

    def test_alias_saas_resolves(self) -> None:
        result = get_template_dir("saas")
        assert result.name == "ai-saas"


class TestStartapiCommand:
    """Test the startapi management command integration."""

    def test_command_import(self) -> None:
        from django_matt.management.commands.startapi import Command

        cmd = Command()
        assert cmd.help

    def test_list_templates_flag(self) -> None:
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("startapi", "--list-templates", stdout=out)
        output = out.getvalue()
        assert "api-only" in output
        assert "ai-saas" in output
        assert "marketplace" in output
        assert "internal-tools" in output

    def test_startapi_with_template(self, tmp_path: Path) -> None:
        from django.core.management import call_command

        project_name = "testproj"
        call_command(
            "startapi",
            project_name,
            "--template",
            "api-only",
            "--directory",
            str(tmp_path),
        )
        output_dir = tmp_path / project_name
        assert output_dir.exists()
        assert (output_dir / "manage.py").exists()
        assert (output_dir / "config" / "settings.py").exists()

    @pytest.mark.parametrize("template", TEMPLATE_NAMES)
    def test_startapi_each_template(self, template: str, tmp_path: Path) -> None:
        from django.core.management import call_command

        project_name = f"test_{template.replace('-', '_')}"
        call_command(
            "startapi",
            project_name,
            "--template",
            template,
            "--directory",
            str(tmp_path),
        )
        output_dir = tmp_path / project_name
        assert output_dir.exists()
        assert (output_dir / "manage.py").exists()
        assert (output_dir / f"{project_name}_app" / "models.py").exists()


class TestTemplateSpecificContent:
    """Test template-specific content is correct."""

    def test_ai_saas_has_celery_config(self, tmp_path: Path) -> None:
        output = render_template("ai-saas", "aiapp", tmp_path / "aiapp")
        settings = (output / "config" / "settings.py").read_text()
        assert "CELERY_BROKER_URL" in settings

    def test_ai_saas_has_ai_config(self, tmp_path: Path) -> None:
        output = render_template("ai-saas", "aiapp", tmp_path / "aiapp")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_AI" in settings

    def test_ai_saas_has_streaming_config(self, tmp_path: Path) -> None:
        output = render_template("ai-saas", "aiapp", tmp_path / "aiapp")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_STREAMING" in settings

    def test_marketplace_has_multitenancy(self, tmp_path: Path) -> None:
        output = render_template("marketplace", "shop", tmp_path / "shop")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_MULTITENANCY" in settings

    def test_marketplace_has_billing_connect(self, tmp_path: Path) -> None:
        output = render_template("marketplace", "shop", tmp_path / "shop")
        settings = (output / "config" / "settings.py").read_text()
        assert "CONNECT_ENABLED" in settings

    def test_marketplace_has_file_uploads(self, tmp_path: Path) -> None:
        output = render_template("marketplace", "shop", tmp_path / "shop")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_FILES" in settings

    def test_internal_tools_has_unfold(self, tmp_path: Path) -> None:
        output = render_template("internal-tools", "tools", tmp_path / "tools")
        settings = (output / "config" / "settings.py").read_text()
        assert "unfold" in settings
        assert "UNFOLD" in settings

    def test_internal_tools_has_audit(self, tmp_path: Path) -> None:
        output = render_template("internal-tools", "tools", tmp_path / "tools")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_AUDIT" in settings

    def test_internal_tools_has_flags(self, tmp_path: Path) -> None:
        output = render_template("internal-tools", "tools", tmp_path / "tools")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_FLAGS" in settings

    def test_internal_tools_has_sso(self, tmp_path: Path) -> None:
        output = render_template("internal-tools", "tools", tmp_path / "tools")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_SSO" in settings

    def test_internal_tools_has_admin_urls(self, tmp_path: Path) -> None:
        output = render_template("internal-tools", "tools", tmp_path / "tools")
        urls = (output / "config" / "urls.py").read_text()
        assert "admin.site.urls" in urls

    def test_api_only_minimal_settings(self, tmp_path: Path) -> None:
        output = render_template("api-only", "minimal", tmp_path / "minimal")
        settings = (output / "config" / "settings.py").read_text()
        assert "DJANGO_MATT_JWT" in settings
        # Should NOT have heavy configs
        assert "CELERY_BROKER_URL" not in settings
        assert "DJANGO_MATT_AI" not in settings
        assert "DJANGO_MATT_MULTITENANCY" not in settings
