"""
Schema-driven form handling for pages.

Provides form validation that works seamlessly with frontend
Zod schemas generated from Pydantic models.
"""

from typing import Any


class PageForm:
    """
    Schema-driven form for page views.

    Uses Pydantic models for validation, which maps directly
    to the Zod schemas generated for the frontend.

    Usage:
        from pydantic import BaseModel, EmailStr

        class UserCreateInput(BaseModel):
            email: EmailStr
            name: str
            password: str

        @page("UserCreate")
        def user_create(request):
            if request.method == "POST":
                form = PageForm(UserCreateInput, request.POST)

                if form.is_valid():
                    user = User.objects.create(**form.validated_data)
                    return redirect_page("/users")

                return PageResponse(
                    "UserCreate",
                    props={"values": form.data},
                    errors=form.errors,
                    status=422,
                )

            return PageResponse("UserCreate")
    """

    def __init__(
        self,
        schema: type,
        data: dict[str, Any] | None = None,
        *,
        instance: Any | None = None,
    ):
        """
        Initialize the form.

        Args:
            schema: Pydantic model class for validation
            data: Form data (usually request.POST)
            instance: Optional existing instance for updates
        """
        self.schema = schema
        self.data = dict(data) if data else {}
        self.instance = instance
        self._validated_data: dict[str, Any] | None = None
        self._errors: dict[str, list[str]] = {}
        self._is_validated = False

    def is_valid(self) -> bool:
        """
        Validate the form data against the schema.

        Returns:
            True if validation passed, False otherwise
        """
        if self._is_validated:
            return len(self._errors) == 0

        self._is_validated = True
        self._errors = {}
        self._validated_data = None

        try:
            from pydantic import BaseModel, ValidationError

            if not issubclass(self.schema, BaseModel):
                raise TypeError(f"Schema must be a Pydantic model, got {self.schema}")

            # Validate with Pydantic
            validated = self.schema(**self.data)
            self._validated_data = validated.model_dump()
            return True

        except ValidationError as e:
            # Convert Pydantic errors to our format
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]

                if field not in self._errors:
                    self._errors[field] = []
                self._errors[field].append(message)

            return False

        except Exception as e:
            self._errors["__all__"] = [str(e)]
            return False

    @property
    def validated_data(self) -> dict[str, Any]:
        """
        Get the validated data.

        Raises:
            ValueError: If form hasn't been validated or validation failed
        """
        if not self._is_validated:
            raise ValueError("Call is_valid() before accessing validated_data")
        if self._validated_data is None:
            raise ValueError("Cannot access validated_data when form is invalid")
        return self._validated_data

    @property
    def errors(self) -> dict[str, list[str]]:
        """
        Get validation errors.

        Format: {"field_name": ["error message 1", "error message 2"]}
        """
        if not self._is_validated:
            self.is_valid()
        return self._errors

    def get_initial_values(self) -> dict[str, Any]:
        """
        Get initial values for the form.

        If an instance is provided, returns its data.
        Otherwise, returns the schema's default values.
        """
        if self.instance:
            # Try to get data from instance
            try:
                from pydantic import BaseModel

                if isinstance(self.instance, BaseModel):
                    return self.instance.model_dump()

                # Django model
                if hasattr(self.instance, "__dict__"):
                    return {
                        k: v for k, v in self.instance.__dict__.items() if not k.startswith("_")
                    }
            except Exception:
                pass

        # Get defaults from schema
        try:
            from pydantic import BaseModel

            if issubclass(self.schema, BaseModel):
                # Get field defaults
                defaults = {}
                for field_name, field_info in self.schema.model_fields.items():
                    if field_info.default is not None:
                        defaults[field_name] = field_info.default
                    elif field_info.default_factory is not None:
                        defaults[field_name] = field_info.default_factory()
                    else:
                        defaults[field_name] = None
                return defaults
        except Exception:
            pass

        return {}


class PageFormSet:
    """
    Handle multiple forms/items (like Django formsets).

    Usage:
        class ItemInput(BaseModel):
            name: str
            quantity: int

        @page("OrderCreate")
        def order_create(request):
            if request.method == "POST":
                formset = PageFormSet(ItemInput, request.POST.getlist("items"))

                if formset.is_valid():
                    for item_data in formset.validated_data:
                        OrderItem.objects.create(**item_data)
                    return redirect_page("/orders")

                return PageResponse(
                    "OrderCreate",
                    props={"items": formset.data},
                    errors={"items": formset.errors},
                    status=422,
                )

            return PageResponse("OrderCreate")
    """

    def __init__(
        self,
        schema: type,
        data: list[dict[str, Any]] | None = None,
        *,
        min_items: int = 0,
        max_items: int | None = None,
    ):
        self.schema = schema
        self.data = list(data) if data else []
        self.min_items = min_items
        self.max_items = max_items
        self._validated_data: list[dict[str, Any]] | None = None
        self._errors: list[dict[str, list[str]]] = []
        self._global_errors: list[str] = []
        self._is_validated = False

    def is_valid(self) -> bool:
        """Validate all items in the formset."""
        if self._is_validated:
            return len(self._global_errors) == 0 and all(len(e) == 0 for e in self._errors)

        self._is_validated = True
        self._errors = []
        self._global_errors = []
        self._validated_data = []

        # Check item count
        if len(self.data) < self.min_items:
            self._global_errors.append(f"At least {self.min_items} items required")

        if self.max_items and len(self.data) > self.max_items:
            self._global_errors.append(f"At most {self.max_items} items allowed")

        # Validate each item
        for item_data in self.data:
            form = PageForm(self.schema, item_data)
            if form.is_valid():
                self._validated_data.append(form.validated_data)
                self._errors.append({})
            else:
                self._errors.append(form.errors)

        return len(self._global_errors) == 0 and all(len(e) == 0 for e in self._errors)

    @property
    def validated_data(self) -> list[dict[str, Any]]:
        """Get validated data for all items."""
        if not self._is_validated:
            raise ValueError("Call is_valid() before accessing validated_data")
        if self._validated_data is None:
            raise ValueError("Cannot access validated_data when formset is invalid")
        return self._validated_data

    @property
    def errors(self) -> list[dict[str, list[str]]]:
        """Get errors for each item."""
        if not self._is_validated:
            self.is_valid()
        return self._errors

    @property
    def global_errors(self) -> list[str]:
        """Get global formset errors (not per-item)."""
        if not self._is_validated:
            self.is_valid()
        return self._global_errors


def form_errors_to_dict(errors: dict[str, Any] | list[Any] | Exception) -> dict[str, list[str]]:
    """
    Convert various error formats to the standard page errors format.

    Supports:
    - Django form errors
    - Pydantic ValidationError
    - Dict of errors
    - Exception with message
    """
    result: dict[str, list[str]] = {}

    # Django form errors
    if hasattr(errors, "get_json_data"):
        for field, field_errors in errors.get_json_data().items():
            result[field] = [e["message"] for e in field_errors]
        return result

    # Pydantic ValidationError
    try:
        from pydantic import ValidationError

        if isinstance(errors, ValidationError):
            for error in errors.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                if field not in result:
                    result[field] = []
                result[field].append(error["msg"])
            return result
    except ImportError:
        pass

    # Dict
    if isinstance(errors, dict):
        for field, messages in errors.items():
            if isinstance(messages, str):
                result[field] = [messages]
            elif isinstance(messages, list):
                result[field] = [str(m) for m in messages]
            else:
                result[field] = [str(messages)]
        return result

    # Exception
    if isinstance(errors, Exception):
        result["__all__"] = [str(errors)]
        return result

    # List of errors
    if isinstance(errors, list):
        result["__all__"] = [str(e) for e in errors]
        return result

    # Unknown format
    result["__all__"] = [str(errors)]
    return result


__all__ = [
    "PageForm",
    "PageFormSet",
    "form_errors_to_dict",
]
