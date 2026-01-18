"""
Test template generation.
"""

from django_matt.cli.templates.utils import pluralize


def generate_test_template(name: str, test_type: str = "controller") -> str:
    """
    Generate a test file template.

    Args:
        name: The model/resource name (e.g., "Product", "User")
        test_type: Type of tests to generate ("controller", "service", or "unit")

    Returns:
        Python code for the tests
    """
    name_lower = name.lower()
    name_plural = pluralize(name_lower)

    lines = [
        '"""',
        f"Tests for {name}.",
        '"""',
        "",
        "import pytest",
        "from django.test import AsyncClient",
        "",
        "",
        "@pytest.mark.django_db",
        f"class Test{name}:",
        f'    """Tests for {name}."""',
        "",
    ]

    if test_type == "controller":
        lines.extend(_generate_controller_tests(name, name_lower, name_plural))
    elif test_type == "service":
        lines.extend(_generate_service_tests(name, name_lower, name_plural))
    else:
        lines.extend(_generate_unit_tests(name_lower))

    return "\n".join(lines)


def _generate_controller_tests(name: str, name_lower: str, name_plural: str) -> list[str]:
    """Generate controller/API tests."""
    return [
        f'    base_url = "/api/{name_plural}"',
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_list_{name_plural}(self, async_client: AsyncClient):",
        f'        """Test listing {name} objects."""',
        "        response = await async_client.get(self.base_url)",
        "        assert response.status_code == 200",
        "        data = response.json()",
        '        assert "items" in data',
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_create_{name_lower}(self, async_client: AsyncClient):",
        f'        """Test creating a {name}."""',
        "        payload = {",
        "            # TODO: Add test data",
        "        }",
        "        response = await async_client.post(self.base_url, json=payload)",
        "        assert response.status_code in [200, 201]",
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_get_{name_lower}(self, async_client: AsyncClient):",
        f'        """Test getting a single {name}."""',
        f"        # TODO: Create a {name} first",
        "        item_id = 1",
        '        response = await async_client.get(f"{self.base_url}/{item_id}")',
        "        assert response.status_code == 200",
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_update_{name_lower}(self, async_client: AsyncClient):",
        f'        """Test updating a {name}."""',
        f"        # TODO: Create a {name} first",
        "        item_id = 1",
        "        payload = {",
        "            # TODO: Add update data",
        "        }",
        '        response = await async_client.put(f"{self.base_url}/{item_id}", json=payload)',
        "        assert response.status_code == 200",
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_delete_{name_lower}(self, async_client: AsyncClient):",
        f'        """Test deleting a {name}."""',
        f"        # TODO: Create a {name} first",
        "        item_id = 1",
        '        response = await async_client.delete(f"{self.base_url}/{item_id}")',
        "        assert response.status_code == 200",
    ]


def _generate_service_tests(name: str, name_lower: str, name_plural: str) -> list[str]:
    """Generate service layer tests."""
    return [
        f"    # from .{name_lower}_service import {name}Service",
        "",
        "    @pytest.fixture",
        "    def service(self):",
        f'        """Create a {name}Service instance."""',
        f"        # return {name}Service()",
        "        pass",
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_list_{name_plural}(self, service):",
        f'        """Test listing {name} objects."""',
        "        # items, total = await service.list()",
        "        # assert isinstance(items, list)",
        "        pass",
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_create_{name_lower}(self, service):",
        f'        """Test creating a {name}."""',
        f"        # data = {name}CreateSchema(...)",
        "        # item = await service.create(data)",
        "        # assert item is not None",
        "        pass",
        "",
        "    @pytest.mark.asyncio",
        f"    async def test_get_{name_lower}(self, service):",
        f'        """Test getting a {name}."""',
        "        # item = await service.get(1)",
        "        # assert item is not None",
        "        pass",
    ]


def _generate_unit_tests(name_lower: str) -> list[str]:
    """Generate basic unit tests."""
    return [
        f"    def test_{name_lower}_example(self):",
        f'        """Example unit test for {name_lower}."""',
        "        # TODO: Add your unit tests",
        "        assert True",
        "",
        f"    def test_{name_lower}_validation(self):",
        f'        """Test {name_lower} validation."""',
        "        # TODO: Add validation tests",
        "        assert True",
    ]
