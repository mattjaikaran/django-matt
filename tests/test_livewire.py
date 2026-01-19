"""Tests for django_matt.livewire module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ValidationError


# =============================================================================
# DECORATOR TESTS
# =============================================================================


class TestActionDecorator:
    """Tests for @action decorator."""

    def test_action_marks_function(self):
        """Test that @action marks function as an action."""
        from django_matt.livewire.component import action

        @action
        def my_action(self):
            pass

        # Action decorator sets _is_action on the wrapper
        assert hasattr(my_action, "_is_action")
        assert my_action._is_action is True

    def test_action_preserves_function_name(self):
        """Test that @action preserves the original function name."""
        from django_matt.livewire.component import action

        @action
        def increment(self):
            return "done"

        assert increment.__name__ == "increment"

    def test_action_stores_original(self):
        """Test that @action stores reference to original function."""
        from django_matt.livewire.component import action

        def original_func(self):
            return "result"

        wrapped = action(original_func)
        assert hasattr(wrapped, "_original")
        assert wrapped._original is original_func


class TestComputedDecorator:
    """Tests for @computed decorator."""

    def test_computed_returns_property(self):
        """Test that @computed returns a property."""
        from django_matt.livewire.component import computed

        @computed
        def full_name(self):
            return "John Doe"

        # computed returns a property object
        assert isinstance(full_name, property)

    def test_computed_marks_fget(self):
        """Test that @computed marks fget with _is_computed."""
        from django_matt.livewire.component import computed

        @computed
        def get_value(self):
            return 42

        # The property's fget has _is_computed
        assert hasattr(get_value.fget, "_is_computed")
        assert get_value.fget._is_computed is True


class TestWatchDecorator:
    """Tests for @watch decorator."""

    def test_watch_marks_function(self):
        """Test that @watch marks function with watched fields."""
        from django_matt.livewire.component import watch

        @watch("count")
        def on_count_change(self, old_value, new_value):
            pass

        assert hasattr(on_count_change, "_watch_fields")
        assert "count" in on_count_change._watch_fields

    def test_watch_multiple_properties(self):
        """Test @watch with multiple properties."""
        from django_matt.livewire.component import watch

        @watch("count", "name")
        def on_change(self, old_value, new_value):
            pass

        assert on_change._watch_fields == ("count", "name")


class TestLifecycleDecorators:
    """Tests for lifecycle decorators."""

    def test_on_mount_decorator(self):
        """Test @on_mount marks function with lifecycle."""
        from django_matt.livewire.component import on_mount

        @on_mount
        def setup(self):
            pass

        assert hasattr(setup, "_lifecycle")
        assert setup._lifecycle == "mount"

    def test_on_hydrate_decorator(self):
        """Test @on_hydrate marks function with lifecycle."""
        from django_matt.livewire.component import on_hydrate

        @on_hydrate
        def restore(self):
            pass

        assert hasattr(restore, "_lifecycle")
        assert restore._lifecycle == "hydrate"

    def test_on_dehydrate_decorator(self):
        """Test @on_dehydrate marks function with lifecycle."""
        from django_matt.livewire.component import on_dehydrate

        @on_dehydrate
        def cleanup(self):
            pass

        assert hasattr(cleanup, "_lifecycle")
        assert cleanup._lifecycle == "dehydrate"


class TestReactiveDecorator:
    """Tests for @reactive decorator."""

    def test_reactive_returns_value(self):
        """Test that @reactive returns the value unchanged."""
        from django_matt.livewire.component import reactive

        result = reactive(0)
        assert result == 0

        result = reactive("test")
        assert result == "test"


# =============================================================================
# LIVE COMPONENT TESTS
# =============================================================================


class TestLiveComponent:
    """Tests for LiveComponent class."""

    def test_component_creation(self):
        """Test creating a basic LiveComponent."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter()
        assert counter.count == 0

    def test_component_with_initial_state(self):
        """Test creating component with initial state."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter(count=10)
        assert counter.count == 10

    def test_component_state_modification(self):
        """Test modifying component state."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter()
        counter.count = 5
        assert counter.count == 5

    def test_component_with_action(self):
        """Test component with action method."""
        from django_matt.livewire.component import LiveComponent, action

        class Counter(LiveComponent):
            count: int = 0

            @action
            def increment(self):
                self.count += 1

        counter = Counter()
        counter.increment()
        assert counter.count == 1

    def test_component_with_computed_property(self):
        """Test component with computed property."""
        from django_matt.livewire.component import LiveComponent, computed

        class Person(LiveComponent):
            first_name: str = ""
            last_name: str = ""

            @computed
            def full_name(self):
                return f"{self.first_name} {self.last_name}"

        person = Person(first_name="John", last_name="Doe")
        # Computed is a property, so access without ()
        assert person.full_name == "John Doe"

    def test_component_id_generation(self):
        """Test that components get unique IDs."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter1 = Counter()
        counter2 = Counter()

        assert counter1.component_id != counter2.component_id

    def test_component_get_state(self):
        """Test getting component state."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0
            name: str = "test"

        counter = Counter(count=5, name="my_counter")
        state = counter.get_state()
        assert state["count"] == 5
        assert state["name"] == "my_counter"

    def test_component_set_state(self):
        """Test setting component state."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter()
        counter.set_state({"count": 10})
        assert counter.count == 10

    def test_component_serialization(self):
        """Test component can be serialized to dict."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0
            name: str = "test"

        counter = Counter(count=5, name="my_counter")
        data = counter.model_dump()
        assert data["count"] == 5
        assert data["name"] == "my_counter"

    def test_component_actions_registered(self):
        """Test that actions are discovered and registered."""
        from django_matt.livewire.component import LiveComponent, action

        class Counter(LiveComponent):
            count: int = 0

            @action
            def increment(self):
                self.count += 1

            @action
            def decrement(self):
                self.count -= 1

            def not_an_action(self):
                pass

        counter = Counter()
        assert "increment" in Counter._actions
        assert "decrement" in Counter._actions
        assert "not_an_action" not in Counter._actions

    def test_component_call_action(self):
        """Test calling action by name."""
        from django_matt.livewire.component import LiveComponent, action

        class Counter(LiveComponent):
            count: int = 0

            @action
            def increment(self):
                self.count += 1

        counter = Counter()
        counter.call_action("increment")
        assert counter.count == 1

    def test_component_call_unknown_action_raises(self):
        """Test calling unknown action raises ValueError."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter()
        with pytest.raises(ValueError, match="Unknown action"):
            counter.call_action("unknown")

    def test_component_mount(self):
        """Test component mount lifecycle."""
        from django_matt.livewire.component import LiveComponent, on_mount

        mounted = []

        class Counter(LiveComponent):
            count: int = 0

            @on_mount
            def setup(self):
                mounted.append(True)

        counter = Counter()
        counter.mount()
        assert len(mounted) == 1

        # Second mount should not call hook again
        counter.mount()
        assert len(mounted) == 1

    def test_component_hydrate(self):
        """Test component hydrate lifecycle."""
        from django_matt.livewire.component import LiveComponent, on_hydrate

        hydrated = []

        class Counter(LiveComponent):
            count: int = 0

            @on_hydrate
            def restore(self):
                hydrated.append(self.count)

        counter = Counter()
        counter.hydrate({"count": 10})
        assert counter.count == 10
        assert len(hydrated) == 1
        assert hydrated[0] == 10

    def test_component_dehydrate(self):
        """Test component dehydrate lifecycle."""
        from django_matt.livewire.component import LiveComponent, on_dehydrate

        dehydrated = []

        class Counter(LiveComponent):
            count: int = 0

            @on_dehydrate
            def cleanup(self):
                dehydrated.append(self.count)

        counter = Counter(count=5)
        state = counter.dehydrate()
        assert state["count"] == 5
        assert len(dehydrated) == 1

    def test_component_get_checksum(self):
        """Test component checksum generation."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter1 = Counter(count=5)
        counter2 = Counter(count=5)
        counter3 = Counter(count=10)

        # Same state should produce same checksum
        assert counter1.get_checksum() == counter2.get_checksum()
        # Different state should produce different checksum
        assert counter1.get_checksum() != counter3.get_checksum()

    def test_component_dirty_tracking(self):
        """Test that state changes mark component as dirty."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter()
        assert counter._dirty is False

        counter.count = 5
        assert counter._dirty is True

    def test_component_watcher_called_on_change(self):
        """Test watchers are called when watched field changes."""
        from django_matt.livewire.component import LiveComponent, watch

        changes = []

        class Counter(LiveComponent):
            count: int = 0

            @watch("count")
            def on_count_change(self, old_value, new_value):
                changes.append((old_value, new_value))

        counter = Counter()
        counter.count = 5
        assert len(changes) == 1
        assert changes[0] == (0, 5)

        counter.count = 10
        assert len(changes) == 2
        assert changes[1] == (5, 10)

    def test_component_render_context(self):
        """Test getting render context."""
        from django_matt.livewire.component import LiveComponent, computed

        class Counter(LiveComponent):
            count: int = 5

            @computed
            def doubled(self):
                return self.count * 2

        counter = Counter()
        context = counter.get_render_context()

        assert context["count"] == 5
        assert context["component_id"] == counter.component_id
        assert context["component_name"] == "Counter"
        assert context["doubled"] == 10


class TestValidatedComponent:
    """Tests for ValidatedComponent class."""

    def test_validated_component_creation(self):
        """Test creating a ValidatedComponent."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            name: str = ""
            email: str = ""

        form = ContactForm()
        assert form.name == ""
        assert form.email == ""

    def test_validated_component_errors_property(self):
        """Test accessing validation errors."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            name: str = ""

        form = ContactForm()
        assert form.errors == {}

    def test_validated_component_validation_rules(self):
        """Test validation with rules."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            name: str = ""
            email: str = ""

            class Validation:
                name = {"required": True, "min_length": 2}
                email = {"required": True, "email": True}

        form = ContactForm()
        assert form.validate() is False
        assert "name" in form.errors
        assert "email" in form.errors

        form.name = "Jo"
        form.email = "test@example.com"
        form._errors = {}  # Clear errors
        assert form.validate() is True

    def test_validated_component_email_validation(self):
        """Test email validation rule."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            email: str = ""

            class Validation:
                email = {"email": True}

        form = ContactForm()
        form.email = "invalid"
        assert form.validate() is False
        assert "email" in form.errors

        form.email = "test@example.com"
        form._errors = {}
        assert form.validate() is True

    def test_validated_component_min_max_length(self):
        """Test min/max length validation."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            name: str = ""

            class Validation:
                name = {"min_length": 2, "max_length": 10}

        form = ContactForm()
        form.name = "A"
        assert form.validate() is False

        form.name = "ThisIsTooLong"
        form._errors = {}
        assert form.validate() is False

        form.name = "Valid"
        form._errors = {}
        assert form.validate() is True

    def test_validated_component_numeric_validation(self):
        """Test numeric min/max validation."""
        from django_matt.livewire.component import ValidatedComponent

        class NumberForm(ValidatedComponent):
            value: int = 0

            class Validation:
                value = {"min": 0, "max": 100}

        form = NumberForm()
        form.value = -1
        assert form.validate() is False

        form.value = 101
        form._errors = {}
        assert form.validate() is False

        form.value = 50
        form._errors = {}
        assert form.validate() is True

    def test_validated_component_reset(self):
        """Test resetting form."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            name: str = ""
            email: str = ""

        form = ContactForm()
        form.name = "Test"
        form.email = "test@example.com"
        form._errors = {"name": ["error"]}

        form.reset()
        assert form.name == ""
        assert form.email == ""
        assert form.errors == {}

    def test_validated_component_validate_field(self):
        """Test validating single field."""
        from django_matt.livewire.component import ValidatedComponent

        class ContactForm(ValidatedComponent):
            name: str = ""
            email: str = ""

            class Validation:
                name = {"required": True}
                email = {"required": True}

        form = ContactForm()
        form.validate_field("name")
        assert "name" in form.errors
        # Email shouldn't be validated yet
        assert "email" not in form.errors

    def test_validated_component_custom_validator(self):
        """Test custom validator function."""
        from django_matt.livewire.component import ValidatedComponent

        def validate_password(value):
            if len(value) < 8:
                return "Password must be at least 8 characters"
            return None

        class PasswordForm(ValidatedComponent):
            password: str = ""

            class Validation:
                password = {"validator": validate_password}

        form = PasswordForm()
        form.password = "short"
        assert form.validate() is False

        form.password = "longenough"
        form._errors = {}
        assert form.validate() is True


# =============================================================================
# SNAPSHOT TESTS
# =============================================================================


class TestSnapshot:
    """Tests for Snapshot class."""

    def test_snapshot_creation(self):
        """Test creating a snapshot."""
        from django_matt.livewire.state import Snapshot

        snapshot = Snapshot(
            component_name="Counter",
            component_id="abc123",
            state={"count": 5},
            checksum="xyz789",
        )
        assert snapshot.component_name == "Counter"
        assert snapshot.component_id == "abc123"
        assert snapshot.state == {"count": 5}
        assert snapshot.checksum == "xyz789"

    def test_snapshot_default_values(self):
        """Test snapshot default values."""
        from django_matt.livewire.state import Snapshot

        snapshot = Snapshot(
            component_name="Counter",
            component_id="abc123",
            state={},
            checksum="xyz",
        )
        assert snapshot.version == 1
        assert isinstance(snapshot.timestamp, datetime)

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        from django_matt.livewire.state import Snapshot

        snapshot = Snapshot(
            component_name="Counter",
            component_id="abc123",
            state={"count": 5},
            checksum="xyz789",
        )
        result = snapshot.to_dict()
        assert result["name"] == "Counter"
        assert result["id"] == "abc123"
        assert result["state"]["count"] == 5
        assert result["checksum"] == "xyz789"
        assert "ts" in result
        assert "v" in result

    def test_snapshot_from_dict(self):
        """Test creating snapshot from dictionary."""
        from django_matt.livewire.state import Snapshot

        dict_data = {
            "name": "Counter",
            "id": "abc123",
            "state": {"count": 10},
            "checksum": "xyz",
            "ts": "2024-01-01T12:00:00",
            "v": 2,
        }
        snapshot = Snapshot.from_dict(dict_data)
        assert snapshot.component_name == "Counter"
        assert snapshot.component_id == "abc123"
        assert snapshot.state["count"] == 10
        assert snapshot.version == 2

    def test_snapshot_to_json(self):
        """Test converting snapshot to JSON."""
        from django_matt.livewire.state import Snapshot

        snapshot = Snapshot(
            component_name="Counter",
            component_id="abc123",
            state={"count": 5},
            checksum="xyz",
        )
        json_str = snapshot.to_json()
        assert '"name": "Counter"' in json_str
        assert '"count": 5' in json_str

    def test_snapshot_from_json(self):
        """Test creating snapshot from JSON."""
        from django_matt.livewire.state import Snapshot
        import json

        data = {
            "name": "Counter",
            "id": "abc123",
            "state": {"count": 5},
            "checksum": "xyz",
            "ts": "2024-01-01T12:00:00",
            "v": 1,
        }
        json_str = json.dumps(data)
        snapshot = Snapshot.from_json(json_str)
        assert snapshot.component_name == "Counter"
        assert snapshot.state["count"] == 5

    def test_snapshot_to_token(self):
        """Test creating signed token from snapshot."""
        from django_matt.livewire.state import Snapshot

        snapshot = Snapshot(
            component_name="Counter",
            component_id="abc123",
            state={"count": 5},
            checksum="xyz",
        )
        token = snapshot.to_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_snapshot_from_token_roundtrip(self):
        """Test roundtrip: snapshot -> token -> snapshot."""
        from django_matt.livewire.state import Snapshot

        original = Snapshot(
            component_name="Counter",
            component_id="abc123",
            state={"count": 5},
            checksum="xyz",
        )
        token = original.to_token()
        restored = Snapshot.from_token(token)

        assert restored.component_name == original.component_name
        assert restored.component_id == original.component_id
        assert restored.state == original.state
        assert restored.checksum == original.checksum

    def test_snapshot_from_invalid_token_raises(self):
        """Test that invalid token raises ValueError."""
        from django_matt.livewire.state import Snapshot

        with pytest.raises(ValueError, match="Invalid snapshot"):
            Snapshot.from_token("invalid_token")

    def test_snapshot_verify_checksum(self):
        """Test verifying snapshot checksum against component."""
        from django_matt.livewire.state import Snapshot
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        counter = Counter(count=5)
        checksum = counter.get_checksum()

        snapshot = Snapshot(
            component_name="Counter",
            component_id=counter.component_id,
            state={"count": 5},
            checksum=checksum,
        )

        assert snapshot.verify_checksum(counter) is True

        counter.count = 10
        assert snapshot.verify_checksum(counter) is False


# =============================================================================
# STATE TESTS
# =============================================================================


class TestState:
    """Tests for State class."""

    def test_state_creation(self):
        """Test creating a State object."""
        from django_matt.livewire.state import State

        state = State(data={"count": 0, "name": "test"})
        assert state.get("count") == 0
        assert state.get("name") == "test"

    def test_state_default_creation(self):
        """Test creating State with defaults."""
        from django_matt.livewire.state import State

        state = State()
        assert state.data == {}
        assert state.dirty_fields == set()
        assert state.version == 0

    def test_state_get_set(self):
        """Test getting and setting state values."""
        from django_matt.livewire.state import State

        state = State()
        state.set("count", 5)
        assert state.get("count") == 5

    def test_state_get_default(self):
        """Test getting non-existent key returns default."""
        from django_matt.livewire.state import State

        state = State()
        assert state.get("missing") is None
        assert state.get("missing", "default") == "default"

    def test_state_dirty_tracking(self):
        """Test that state tracks dirty fields."""
        from django_matt.livewire.state import State

        state = State(data={"count": 0})
        state.set("count", 5)

        assert "count" in state.dirty_fields
        assert state.is_dirty() is True
        assert state.is_dirty("count") is True
        assert state.is_dirty("other") is False

    def test_state_clear_dirty(self):
        """Test clearing dirty state."""
        from django_matt.livewire.state import State

        state = State(data={"count": 0})
        state.set("count", 5)
        assert state.is_dirty() is True

        state.clear_dirty()
        assert state.is_dirty() is False
        assert len(state.dirty_fields) == 0

    def test_state_get_dirty_values(self):
        """Test getting only dirty values."""
        from django_matt.livewire.state import State

        state = State(data={"a": 1, "b": 2, "c": 3})
        state.set("a", 10)
        state.set("c", 30)

        dirty = state.get_dirty_values()
        assert dirty == {"a": 10, "c": 30}
        assert "b" not in dirty

    def test_state_update(self):
        """Test updating multiple values."""
        from django_matt.livewire.state import State

        state = State()
        state.update({"a": 1, "b": 2, "c": 3})

        assert state.get("a") == 1
        assert state.get("b") == 2
        assert state.get("c") == 3

    def test_state_diff(self):
        """Test getting state diff between two states."""
        from django_matt.livewire.state import State

        state1 = State(data={"a": 1, "b": 2})
        state2 = State(data={"a": 1, "c": 3})  # b removed, c added

        diff = state1.diff(state2)
        assert "b" in diff["added"]  # state1 has b, state2 doesn't
        assert "c" in diff["removed"]  # state2 has c, state1 doesn't

    def test_state_diff_changed(self):
        """Test diff detects changed values."""
        from django_matt.livewire.state import State

        state1 = State(data={"count": 10})
        state2 = State(data={"count": 5})

        diff = state1.diff(state2)
        assert "count" in diff["changed"]
        assert diff["changed"]["count"]["old"] == 5
        assert diff["changed"]["count"]["new"] == 10

    def test_state_clone(self):
        """Test cloning state."""
        from django_matt.livewire.state import State

        original = State(data={"count": 5})
        original.set("count", 10)

        cloned = original.clone()
        assert cloned.data == original.data
        assert cloned.dirty_fields == original.dirty_fields
        assert cloned is not original

    def test_state_version_increment(self):
        """Test that version increments on changes."""
        from django_matt.livewire.state import State

        state = State()
        assert state.version == 0

        state.set("a", 1)
        assert state.version == 1

        state.set("b", 2)
        assert state.version == 2

    def test_state_no_change_no_dirty(self):
        """Test that setting same value doesn't mark dirty."""
        from django_matt.livewire.state import State

        state = State(data={"count": 5})
        state.clear_dirty()

        state.set("count", 5)  # Same value
        assert state.is_dirty("count") is False


# =============================================================================
# STATE MANAGER TESTS
# =============================================================================


class TestStateManager:
    """Tests for StateManager class."""

    def test_state_manager_creation(self):
        """Test creating a StateManager."""
        from django_matt.livewire.state import StateManager

        manager = StateManager()
        assert manager.backend == "memory"
        assert manager.ttl == 3600
        assert manager.max_snapshots == 100

    def test_state_manager_custom_config(self):
        """Test StateManager with custom configuration."""
        from django_matt.livewire.state import StateManager

        manager = StateManager(backend="cache", ttl=1800, max_snapshots=50)
        assert manager.backend == "cache"
        assert manager.ttl == 1800
        assert manager.max_snapshots == 50

    def test_state_manager_save_and_load(self):
        """Test saving and loading component state."""
        from django_matt.livewire.state import StateManager
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        manager = StateManager(backend="memory")
        counter = Counter(count=5)

        snapshot = manager.save(counter)
        assert snapshot.state["count"] == 5
        assert snapshot.component_id == counter.component_id

        loaded = manager.load(counter.component_id)
        assert loaded is not None
        assert loaded.state["count"] == 5

    def test_state_manager_restore(self):
        """Test restoring component state."""
        from django_matt.livewire.state import StateManager
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        manager = StateManager(backend="memory")
        counter = Counter(count=5)

        snapshot = manager.save(counter)

        # Create new component and restore
        new_counter = Counter()
        new_counter._component_id = counter.component_id
        assert manager.restore(new_counter, snapshot) is True
        assert new_counter.count == 5

    def test_state_manager_load_nonexistent(self):
        """Test loading non-existent snapshot."""
        from django_matt.livewire.state import StateManager

        manager = StateManager(backend="memory")
        loaded = manager.load("nonexistent-id")
        assert loaded is None

    def test_state_manager_get_history(self):
        """Test getting snapshot history."""
        from django_matt.livewire.state import StateManager
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        manager = StateManager(backend="memory")
        counter = Counter()

        # Save multiple times
        counter.count = 1
        manager.save(counter)
        counter.count = 2
        manager.save(counter)
        counter.count = 3
        manager.save(counter)

        history = manager.get_history(counter.component_id)
        assert len(history) == 3

    def test_state_manager_clear(self):
        """Test clearing snapshots."""
        from django_matt.livewire.state import StateManager
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        manager = StateManager(backend="memory")
        counter = Counter(count=5)
        manager.save(counter)

        manager.clear(counter.component_id)
        loaded = manager.load(counter.component_id)
        assert loaded is None

    def test_state_manager_clear_all(self):
        """Test clearing all snapshots."""
        from django_matt.livewire.state import StateManager
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        manager = StateManager(backend="memory")

        counter1 = Counter(count=1)
        counter2 = Counter(count=2)
        manager.save(counter1)
        manager.save(counter2)

        manager.clear()
        assert manager.load(counter1.component_id) is None
        assert manager.load(counter2.component_id) is None

    def test_state_manager_max_snapshots(self):
        """Test that max_snapshots is enforced."""
        from django_matt.livewire.state import StateManager
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0

        manager = StateManager(backend="memory", max_snapshots=3)
        counter = Counter()

        # Save 5 times
        for i in range(5):
            counter.count = i
            manager.save(counter)

        history = manager.get_history(counter.component_id)
        assert len(history) == 3  # Only last 3 kept


# =============================================================================
# COMPONENT REGISTRY TESTS
# =============================================================================


class TestComponentRegistry:
    """Tests for ComponentRegistry class."""

    def test_registry_creation(self):
        """Test creating a ComponentRegistry."""
        from django_matt.livewire.registry import ComponentRegistry

        registry = ComponentRegistry()
        assert registry is not None
        assert registry._components == {}

    def test_registry_register_class(self):
        """Test registering a component class directly."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        registry.register_class("counter", Counter)
        assert registry.get("counter") == Counter

    def test_registry_register_with_aliases(self):
        """Test registering a component with aliases."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        registry.register_class("counter", Counter, aliases=["cnt", "count-component"])
        assert registry.get("counter") == Counter
        assert registry.get("cnt") == Counter
        assert registry.get("count-component") == Counter

    def test_registry_get_nonexistent(self):
        """Test getting a non-existent component."""
        from django_matt.livewire.registry import ComponentRegistry

        registry = ComponentRegistry()
        result = registry.get("NonExistent")
        assert result is None

    def test_registry_contains(self):
        """Test checking if component is registered."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        assert "counter" not in registry
        registry.register_class("counter", Counter)
        assert "counter" in registry

    def test_registry_unregister(self):
        """Test unregistering a component."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        registry.register_class("counter", Counter, aliases=["cnt"])
        assert "counter" in registry

        registry.unregister("counter")
        assert "counter" not in registry
        assert "cnt" not in registry  # Aliases also removed

    def test_registry_list_components(self):
        """Test listing all registered components."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        class Timer(LiveComponent):
            seconds: int = 0

        registry.register_class("counter", Counter)
        registry.register_class("timer", Timer)

        names = registry.list()
        assert "counter" in names
        assert "timer" in names

    def test_registry_decorator(self):
        """Test using registry as decorator."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        @registry.register("counter")
        class Counter(LiveComponent):
            count: int = 0

        assert registry.get("counter") == Counter

    def test_registry_decorator_with_aliases(self):
        """Test using registry decorator with aliases."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        @registry.register("counter", aliases=["cnt"])
        class Counter(LiveComponent):
            count: int = 0

        assert registry.get("counter") == Counter
        assert registry.get("cnt") == Counter

    def test_registry_create(self):
        """Test creating component instance from registry."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        registry.register_class("counter", Counter)

        instance = registry.create("counter", count=5)
        assert isinstance(instance, Counter)
        assert instance.count == 5

    def test_registry_create_unknown_raises(self):
        """Test creating unknown component raises ValueError."""
        from django_matt.livewire.registry import ComponentRegistry

        registry = ComponentRegistry()
        with pytest.raises(ValueError, match="Unknown component"):
            registry.create("unknown")

    def test_registry_clear(self):
        """Test clearing all registrations."""
        from django_matt.livewire.registry import ComponentRegistry
        from django_matt.livewire.component import LiveComponent

        registry = ComponentRegistry()

        class Counter(LiveComponent):
            count: int = 0

        registry.register_class("counter", Counter, aliases=["cnt"])
        registry.clear()

        assert registry.list() == []
        assert "counter" not in registry


# =============================================================================
# GLOBAL REGISTRY TESTS
# =============================================================================


class TestGlobalRegistry:
    """Tests for global component registry."""

    def test_global_registry_exists(self):
        """Test that global registry exists."""
        from django_matt.livewire.registry import registry

        assert registry is not None

    def test_global_registry_is_component_registry(self):
        """Test that global registry is ComponentRegistry instance."""
        from django_matt.livewire.registry import registry, ComponentRegistry

        assert isinstance(registry, ComponentRegistry)

    def test_register_component_helper(self):
        """Test register_component convenience function."""
        from django_matt.livewire.registry import register_component
        from django_matt.livewire.component import LiveComponent

        # This is a decorator factory
        decorator = register_component("test-component")
        assert callable(decorator)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestLivewireIntegration:
    """Integration tests for livewire components."""

    def test_full_component_lifecycle(self):
        """Test full component lifecycle."""
        from django_matt.livewire.component import LiveComponent, action, computed, on_mount

        mount_called = []

        class Counter(LiveComponent):
            count: int = 0

            @on_mount
            def setup(self):
                mount_called.append(True)

            @action
            def increment(self):
                self.count += 1

            @action
            def decrement(self):
                self.count -= 1

            @computed
            def doubled(self):
                return self.count * 2

        counter = Counter()
        counter.mount()
        assert len(mount_called) == 1

        # Test actions
        counter.increment()
        assert counter.count == 1

        counter.increment()
        counter.increment()
        assert counter.count == 3

        counter.decrement()
        assert counter.count == 2

        # Test computed (property access, not call)
        assert counter.doubled == 4

    def test_component_with_nested_state(self):
        """Test component with nested state objects."""
        from django_matt.livewire.component import LiveComponent
        from typing import List

        class TodoList(LiveComponent):
            items: List[str] = []
            completed: List[bool] = []

        todo = TodoList()
        todo.items = ["Item 1", "Item 2"]
        todo.completed = [False, True]

        assert len(todo.items) == 2
        assert todo.completed[1] is True

    def test_component_state_serialization_roundtrip(self):
        """Test serializing and deserializing component state."""
        from django_matt.livewire.component import LiveComponent

        class Counter(LiveComponent):
            count: int = 0
            name: str = ""

        # Create component with state
        original = Counter(count=42, name="my_counter")

        # Serialize
        data = original.model_dump()

        # Deserialize
        restored = Counter(**data)

        assert restored.count == 42
        assert restored.name == "my_counter"

    def test_component_validation_integration(self):
        """Test component with Pydantic validation."""
        from django_matt.livewire.component import LiveComponent
        from pydantic import Field

        class BoundedCounter(LiveComponent):
            count: int = Field(default=0, ge=0, le=100)

        counter = BoundedCounter()
        counter.count = 50
        assert counter.count == 50

        # Validation should prevent invalid values
        with pytest.raises(ValidationError):
            BoundedCounter(count=-1)

        with pytest.raises(ValidationError):
            BoundedCounter(count=101)

    def test_snapshot_manager_integration(self):
        """Test snapshot and manager integration."""
        from django_matt.livewire.component import LiveComponent, action
        from django_matt.livewire.state import StateManager

        class Counter(LiveComponent):
            count: int = 0

            @action
            def increment(self):
                self.count += 1

        manager = StateManager(backend="memory")
        counter = Counter()

        # Perform actions and save snapshots
        counter.increment()
        manager.save(counter)

        counter.increment()
        counter.increment()
        manager.save(counter)

        # Load and restore
        latest = manager.load(counter.component_id)
        assert latest.state["count"] == 3

        history = manager.get_history(counter.component_id)
        assert len(history) == 2
        assert history[0].state["count"] == 1
        assert history[1].state["count"] == 3


class TestGlobalStateManager:
    """Tests for global state manager."""

    def test_global_state_manager_exists(self):
        """Test that global state manager exists."""
        from django_matt.livewire.state import state_manager

        assert state_manager is not None

    def test_global_state_manager_is_state_manager(self):
        """Test that global state manager is StateManager instance."""
        from django_matt.livewire.state import state_manager, StateManager

        assert isinstance(state_manager, StateManager)
