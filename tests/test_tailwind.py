"""Tests for django_matt.tailwind module."""

import pytest


# =============================================================================
# CN FUNCTION TESTS
# =============================================================================


class TestCnFunction:
    """Tests for cn() class merging function."""

    def test_cn_basic_merge(self):
        """Test basic class merging."""
        from django_matt.tailwind.utils import cn

        result = cn("px-4", "py-2")
        assert result == "px-4 py-2"

    def test_cn_filters_none(self):
        """Test that cn filters out None values."""
        from django_matt.tailwind.utils import cn

        result = cn("px-4", None, "py-2")
        assert result == "px-4 py-2"

    def test_cn_filters_false(self):
        """Test that cn filters out False values."""
        from django_matt.tailwind.utils import cn

        result = cn("px-4", False, "py-2")
        assert result == "px-4 py-2"

    def test_cn_filters_empty_string(self):
        """Test that cn filters out empty strings."""
        from django_matt.tailwind.utils import cn

        result = cn("px-4", "", "py-2")
        assert result == "px-4 py-2"

    def test_cn_conditional_class(self):
        """Test cn with conditional class."""
        from django_matt.tailwind.utils import cn

        is_active = True
        result = cn("px-4", is_active and "bg-blue-500")
        assert result == "px-4 bg-blue-500"

        is_active = False
        result = cn("px-4", is_active and "bg-blue-500")
        assert result == "px-4"

    def test_cn_conflict_resolution(self):
        """Test that later classes override earlier ones."""
        from django_matt.tailwind.utils import cn

        # Later px-8 should override px-4
        result = cn("px-4", "px-8")
        assert "px-8" in result
        assert "px-4" not in result

    def test_cn_different_categories(self):
        """Test that different categories don't conflict."""
        from django_matt.tailwind.utils import cn

        result = cn("px-4", "py-2", "bg-blue-500")
        assert "px-4" in result
        assert "py-2" in result
        assert "bg-blue-500" in result


# =============================================================================
# MERGE CLASSES TESTS
# =============================================================================


class TestMergeClasses:
    """Tests for merge_classes function."""

    def test_merge_classes_basic(self):
        """Test basic class merging."""
        from django_matt.tailwind.utils import merge_classes

        result = merge_classes("px-4", "py-2")
        assert result == "px-4 py-2"

    def test_merge_classes_with_list(self):
        """Test merging with list argument."""
        from django_matt.tailwind.utils import merge_classes

        result = merge_classes(["px-4", "py-2"], "bg-blue-500")
        assert "px-4" in result
        assert "py-2" in result
        assert "bg-blue-500" in result

    def test_merge_classes_with_variants(self):
        """Test merging preserves variants."""
        from django_matt.tailwind.utils import merge_classes

        result = merge_classes("px-4", "hover:py-8")
        assert "px-4" in result
        assert "hover:py-8" in result

    def test_merge_classes_padding_conflict(self):
        """Test padding conflict resolution."""
        from django_matt.tailwind.utils import merge_classes

        result = merge_classes("p-4", "p-8")
        assert "p-8" in result
        assert result.count("p-") == 1  # Only one padding class

    def test_merge_classes_margin_conflict(self):
        """Test margin conflict resolution."""
        from django_matt.tailwind.utils import merge_classes

        result = merge_classes("m-4", "m-2")
        assert "m-2" in result
        assert result.count("m-") == 1


# =============================================================================
# CLASSES FUNCTION TESTS
# =============================================================================


class TestClassesFunction:
    """Tests for classes() simple join function."""

    def test_classes_basic(self):
        """Test basic class joining."""
        from django_matt.tailwind.utils import classes

        result = classes("px-4", "py-2", "bg-blue-500")
        assert result == "px-4 py-2 bg-blue-500"

    def test_classes_filters_falsy(self):
        """Test that classes filters falsy values."""
        from django_matt.tailwind.utils import classes

        result = classes("px-4", None, "", False, "py-2")
        assert result == "px-4 py-2"

    def test_classes_with_list(self):
        """Test classes with list argument."""
        from django_matt.tailwind.utils import classes

        result = classes("px-4", ["py-2", "bg-blue-500"])
        assert "px-4" in result
        assert "py-2" in result
        assert "bg-blue-500" in result

    def test_classes_no_conflict_resolution(self):
        """Test that classes does NOT resolve conflicts."""
        from django_matt.tailwind.utils import classes

        result = classes("px-4", "px-8")
        assert "px-4" in result
        assert "px-8" in result


# =============================================================================
# CLASS LIST TESTS
# =============================================================================


class TestClassList:
    """Tests for ClassList builder."""

    def test_classlist_basic(self):
        """Test basic ClassList usage."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().add("px-4").add("py-2").build()
        assert "px-4" in result
        assert "py-2" in result

    def test_classlist_initial_classes(self):
        """Test ClassList with initial classes."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList("px-4", "py-2").build()
        assert "px-4" in result
        assert "py-2" in result

    def test_classlist_when_true(self):
        """Test ClassList.when() with true condition."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().add("px-4").when(True, "bg-blue-500").build()
        assert "px-4" in result
        assert "bg-blue-500" in result

    def test_classlist_when_false(self):
        """Test ClassList.when() with false condition."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().add("px-4").when(False, "bg-blue-500").build()
        assert "px-4" in result
        assert "bg-blue-500" not in result

    def test_classlist_unless_true(self):
        """Test ClassList.unless() with true condition."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().add("px-4").unless(True, "hidden").build()
        assert "px-4" in result
        assert "hidden" not in result

    def test_classlist_unless_false(self):
        """Test ClassList.unless() with false condition."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().add("px-4").unless(False, "visible").build()
        assert "px-4" in result
        assert "visible" in result

    def test_classlist_remove(self):
        """Test ClassList.remove()."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().add("px-4", "py-2").remove("py-2").build()
        assert "px-4" in result
        assert "py-2" not in result

    def test_classlist_toggle(self):
        """Test ClassList.toggle()."""
        from django_matt.tailwind.utils import ClassList

        result = ClassList().toggle(True, "visible", "hidden").build()
        assert "visible" in result
        assert "hidden" not in result

        result = ClassList().toggle(False, "visible", "hidden").build()
        assert "hidden" in result
        assert "visible" not in result

    def test_classlist_str(self):
        """Test ClassList.__str__()."""
        from django_matt.tailwind.utils import ClassList

        cl = ClassList().add("px-4")
        assert str(cl) == cl.build()

    def test_classlist_chaining(self):
        """Test method chaining returns self."""
        from django_matt.tailwind.utils import ClassList

        cl = ClassList()
        assert cl.add("px-4") is cl
        assert cl.when(True, "py-2") is cl
        assert cl.unless(False, "mt-4") is cl
        assert cl.remove("mt-4") is cl
        assert cl.toggle(True, "flex") is cl


# =============================================================================
# CLASS BUILDER TESTS
# =============================================================================


class TestClassBuilder:
    """Tests for ClassBuilder with variant support."""

    def test_classbuilder_base(self):
        """Test ClassBuilder base classes."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("px-4 py-2").build()
        assert "px-4" in result
        assert "py-2" in result

    def test_classbuilder_variant(self):
        """Test ClassBuilder variant classes."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("px-4").variant("hover", "bg-blue-600").build()
        assert "px-4" in result
        assert "hover:bg-blue-600" in result

    def test_classbuilder_hover(self):
        """Test ClassBuilder hover shortcut."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("bg-blue-500").hover("bg-blue-600").build()
        assert "bg-blue-500" in result
        assert "hover:bg-blue-600" in result

    def test_classbuilder_focus(self):
        """Test ClassBuilder focus shortcut."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("border").focus("ring-2").build()
        assert "border" in result
        assert "focus:ring-2" in result

    def test_classbuilder_active(self):
        """Test ClassBuilder active shortcut."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("bg-blue-500").active("bg-blue-700").build()
        assert "bg-blue-500" in result
        assert "active:bg-blue-700" in result

    def test_classbuilder_disabled(self):
        """Test ClassBuilder disabled shortcut."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("bg-blue-500").disabled("opacity-50").build()
        assert "bg-blue-500" in result
        assert "disabled:opacity-50" in result

    def test_classbuilder_dark(self):
        """Test ClassBuilder dark mode shortcut."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("bg-white").dark("bg-gray-900").build()
        assert "bg-white" in result
        assert "dark:bg-gray-900" in result

    def test_classbuilder_responsive(self):
        """Test ClassBuilder responsive shortcuts."""
        from django_matt.tailwind.utils import ClassBuilder

        result = (
            ClassBuilder()
            .base("flex-col")
            .sm("flex-row")
            .md("gap-4")
            .lg("gap-6")
            .xl("gap-8")
            .build()
        )
        assert "flex-col" in result
        assert "sm:flex-row" in result
        assert "md:gap-4" in result
        assert "lg:gap-6" in result
        assert "xl:gap-8" in result

    def test_classbuilder_str(self):
        """Test ClassBuilder.__str__()."""
        from django_matt.tailwind.utils import ClassBuilder

        cb = ClassBuilder().base("px-4")
        assert str(cb) == cb.build()

    def test_classbuilder_multiple_variant_classes(self):
        """Test ClassBuilder with multiple classes per variant."""
        from django_matt.tailwind.utils import ClassBuilder

        result = ClassBuilder().base("px-4").hover("bg-blue-600", "text-white").build()
        assert "hover:bg-blue-600" in result
        assert "hover:text-white" in result


# =============================================================================
# COMPONENT CLASSES TESTS
# =============================================================================


class TestComponentClasses:
    """Tests for pre-built component classes."""

    def test_button_classes_exist(self):
        """Test ButtonClasses can be imported."""
        from django_matt.tailwind.components import ButtonClasses

        assert ButtonClasses is not None
        assert hasattr(ButtonClasses, "get")
        assert hasattr(ButtonClasses, "primary")

    def test_button_classes_primary(self):
        """Test ButtonClasses.primary()."""
        from django_matt.tailwind.components import ButtonClasses

        classes = ButtonClasses.primary()
        assert len(classes) > 0
        assert "inline-flex" in classes

    def test_button_classes_secondary(self):
        """Test ButtonClasses.secondary()."""
        from django_matt.tailwind.components import ButtonClasses

        classes = ButtonClasses.secondary()
        assert len(classes) > 0

    def test_button_classes_sizes(self):
        """Test ButtonClasses sizes."""
        from django_matt.tailwind.components import ButtonClasses

        sm = ButtonClasses.primary(size="sm")
        md = ButtonClasses.primary(size="md")
        lg = ButtonClasses.primary(size="lg")

        assert len(sm) > 0
        assert len(md) > 0
        assert len(lg) > 0

    def test_input_classes_exist(self):
        """Test InputClasses can be imported."""
        from django_matt.tailwind.components import InputClasses

        assert InputClasses is not None

    def test_card_classes_exist(self):
        """Test CardClasses can be imported."""
        from django_matt.tailwind.components import CardClasses

        assert CardClasses is not None

    def test_alert_classes_exist(self):
        """Test AlertClasses can be imported."""
        from django_matt.tailwind.components import AlertClasses

        assert AlertClasses is not None


# =============================================================================
# CONFIG TESTS
# =============================================================================


class TestTailwindConfig:
    """Tests for Tailwind configuration."""

    def test_tailwind_config_creation(self):
        """Test creating TailwindConfig."""
        from django_matt.tailwind.config import TailwindConfig

        config = TailwindConfig()
        assert config is not None

    def test_tailwind_config_has_colors(self):
        """Test TailwindConfig has color settings."""
        from django_matt.tailwind.config import TailwindConfig

        config = TailwindConfig()
        assert hasattr(config, "color_primary")
        assert hasattr(config, "color_secondary")

    def test_get_tailwind_config(self):
        """Test get_tailwind_config function."""
        from django_matt.tailwind.config import get_tailwind_config

        config = get_tailwind_config()
        assert config is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestTailwindIntegration:
    """Integration tests for Tailwind utilities."""

    def test_build_button_with_state(self):
        """Test building button classes with state."""
        from django_matt.tailwind.utils import ClassBuilder

        is_loading = True
        is_disabled = False

        result = (
            ClassBuilder()
            .base("px-4 py-2 rounded font-medium")
            .base("bg-blue-500 text-white")
            .hover("bg-blue-600")
            .focus("ring-2 ring-blue-500 ring-offset-2")
            .disabled("opacity-50 cursor-not-allowed")
            .build()
        )

        assert "px-4" in result
        assert "hover:bg-blue-600" in result
        assert "focus:ring-2" in result
        assert "disabled:opacity-50" in result

    def test_conditional_classes_pattern(self):
        """Test common conditional classes pattern."""
        from django_matt.tailwind.utils import cn

        is_active = True
        is_error = False
        size = "lg"

        result = cn(
            "px-4 py-2 rounded",
            is_active and "bg-blue-500",
            is_error and "border-red-500",
            size == "lg" and "text-lg",
            size == "sm" and "text-sm",
        )

        assert "bg-blue-500" in result
        assert "border-red-500" not in result
        assert "text-lg" in result
        assert "text-sm" not in result

    def test_responsive_layout(self):
        """Test building responsive layout classes."""
        from django_matt.tailwind.utils import ClassBuilder

        result = (
            ClassBuilder()
            .base("flex flex-col gap-4")
            .sm("flex-row")
            .md("gap-6")
            .lg("gap-8")
            .build()
        )

        assert "flex flex-col" in result
        assert "sm:flex-row" in result
        assert "md:gap-6" in result
        assert "lg:gap-8" in result
