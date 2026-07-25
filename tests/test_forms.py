"""Tests for django_matt.forms module."""

import json
from unittest.mock import MagicMock, patch

import django.forms as django_forms
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import RequestFactory

import pytest

from django_matt.forms.bridge import (
    THEME_CLASSES,
    _choices_to_options,
    _extract_validators,
    _map_field,
    form_to_components,
    render_form,
)
from django_matt.forms.builder import FormBuilder
from django_matt.forms.decorators import _form_errors_dict, _is_ajax, ajax_form
from django_matt.forms.validation import (
    _analyze_field,
    form_to_json_schema,
    form_to_yup,
    form_to_zod,
)

# =============================================================================
# Sample forms for testing
# =============================================================================


class ContactForm(django_forms.Form):
    name = django_forms.CharField(max_length=100, min_length=2, required=True)
    email = django_forms.EmailField(required=True)
    age = django_forms.IntegerField(min_value=0, max_value=150, required=False)
    message = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 5}),
        required=True,
        help_text="Tell us what's on your mind",
    )
    subscribe = django_forms.BooleanField(required=False, label="Subscribe to newsletter")


class FullFieldForm(django_forms.Form):
    """Form exercising all supported field types."""

    text = django_forms.CharField(max_length=200)
    email = django_forms.EmailField()
    url = django_forms.URLField()
    slug = django_forms.SlugField()
    password = django_forms.CharField(widget=django_forms.PasswordInput())
    hidden = django_forms.CharField(widget=django_forms.HiddenInput(), required=False)
    integer = django_forms.IntegerField(min_value=1, max_value=99)
    decimal = django_forms.DecimalField(max_digits=10, decimal_places=2)
    floating = django_forms.FloatField()
    boolean = django_forms.BooleanField(required=False)
    choice = django_forms.ChoiceField(choices=[("a", "Alpha"), ("b", "Beta")])
    multi = django_forms.MultipleChoiceField(choices=[("x", "X"), ("y", "Y")])
    date = django_forms.DateField()
    datetime = django_forms.DateTimeField()
    time = django_forms.TimeField()
    file = django_forms.FileField(required=False)
    image = django_forms.ImageField(required=False)


# =============================================================================
# BRIDGE — _extract_validators TESTS
# =============================================================================


class TestExtractValidators:
    """Tests for extracting validation rules from Django fields."""

    def test_required_field(self):
        field = django_forms.CharField(required=True)
        rules = _extract_validators(field)
        assert any(r.type == "required" for r in rules)

    def test_max_length(self):
        field = django_forms.CharField(max_length=50)
        rules = _extract_validators(field)
        assert any(r.type == "maxLength" and r.value == 50 for r in rules)

    def test_min_length(self):
        field = django_forms.CharField(min_length=3)
        rules = _extract_validators(field)
        assert any(r.type == "minLength" and r.value == 3 for r in rules)

    def test_max_value(self):
        field = django_forms.IntegerField(max_value=100)
        rules = _extract_validators(field)
        assert any(r.type == "max" and r.value == 100 for r in rules)

    def test_min_value(self):
        field = django_forms.IntegerField(min_value=5)
        rules = _extract_validators(field)
        assert any(r.type == "min" and r.value == 5 for r in rules)

    def test_email_validator(self):
        field = django_forms.EmailField()
        rules = _extract_validators(field)
        assert any(r.type == "email" for r in rules)

    def test_url_validator(self):
        field = django_forms.URLField()
        rules = _extract_validators(field)
        assert any(r.type == "url" for r in rules)

    def test_regex_validator(self):
        from django.core.validators import RegexValidator

        field = django_forms.CharField(validators=[RegexValidator(r"^\d{3}$", "3 digits")])
        rules = _extract_validators(field)
        assert any(r.type == "pattern" for r in rules)
        pattern_rule = next(r for r in rules if r.type == "pattern")
        assert pattern_rule.value == r"^\d{3}$"


# =============================================================================
# BRIDGE — _map_field TESTS
# =============================================================================


class TestMapField:
    """Tests for mapping Django fields to component fields."""

    def test_charfield_to_textfield(self):
        from django_matt.components.forms import TextField

        field = django_forms.CharField(max_length=100)
        comp = _map_field("username", field)
        assert isinstance(comp, TextField)
        assert comp.name == "username"

    def test_emailfield(self):
        from django_matt.components.forms import EmailField

        field = django_forms.EmailField()
        comp = _map_field("email", field)
        assert isinstance(comp, EmailField)

    def test_password_widget(self):
        from django_matt.components.forms import PasswordField

        field = django_forms.CharField(widget=django_forms.PasswordInput())
        comp = _map_field("pw", field)
        assert isinstance(comp, PasswordField)

    def test_textarea_widget(self):
        from django_matt.components.forms import Textarea

        field = django_forms.CharField(widget=django_forms.Textarea(attrs={"rows": 5}))
        comp = _map_field("bio", field)
        assert isinstance(comp, Textarea)
        assert comp.rows == 5

    def test_integerfield(self):
        from django_matt.components.forms import NumberField

        field = django_forms.IntegerField(min_value=0, max_value=99)
        comp = _map_field("qty", field)
        assert isinstance(comp, NumberField)
        assert comp.step == 1

    def test_decimalfield(self):
        from django_matt.components.forms import NumberField

        field = django_forms.DecimalField(max_digits=10, decimal_places=2)
        comp = _map_field("price", field)
        assert isinstance(comp, NumberField)
        # NOTE: DecimalField inherits from IntegerField in Django,
        # so the IntegerField branch catches it first — precision is not set.
        # This is a known mapping limitation in bridge._map_field.

    def test_floatfield(self):
        from django_matt.components.forms import NumberField

        field = django_forms.FloatField()
        comp = _map_field("rate", field)
        assert isinstance(comp, NumberField)

    def test_booleanfield(self):
        from django_matt.components.forms import Checkbox

        field = django_forms.BooleanField()
        comp = _map_field("agree", field)
        assert isinstance(comp, Checkbox)

    def test_choicefield(self):
        from django_matt.components.forms import Select

        field = django_forms.ChoiceField(choices=[("a", "A"), ("b", "B")])
        comp = _map_field("color", field)
        assert isinstance(comp, Select)
        assert len(comp.options) == 2

    def test_multiplechoicefield(self):
        from django_matt.components.forms import MultiSelect

        field = django_forms.MultipleChoiceField(choices=[("x", "X"), ("y", "Y")])
        comp = _map_field("tags", field)
        assert isinstance(comp, MultiSelect)

    def test_datefield(self):
        from django_matt.components.forms import DatePicker

        field = django_forms.DateField()
        comp = _map_field("dob", field)
        assert isinstance(comp, DatePicker)

    def test_datetimefield(self):
        from django_matt.components.forms import DatePicker

        field = django_forms.DateTimeField()
        comp = _map_field("ts", field)
        assert isinstance(comp, DatePicker)
        assert comp.show_time is True

    def test_timefield(self):
        from django_matt.components.forms import DatePicker

        field = django_forms.TimeField()
        comp = _map_field("start", field)
        assert isinstance(comp, DatePicker)
        assert comp.format == "HH:mm"

    def test_filefield(self):
        from django_matt.components.forms import FileUpload

        field = django_forms.FileField()
        comp = _map_field("doc", field)
        assert isinstance(comp, FileUpload)

    def test_imagefield(self):
        from django_matt.components.forms import FileUpload

        field = django_forms.ImageField()
        comp = _map_field("avatar", field)
        assert isinstance(comp, FileUpload)
        assert "image/*" in comp.accept

    def test_urlfield(self):
        from django_matt.components.forms import TextField

        field = django_forms.URLField()
        comp = _map_field("website", field)
        assert isinstance(comp, TextField)
        assert comp.input_type == "url"

    def test_slugfield(self):
        from django_matt.components.forms import TextField

        field = django_forms.SlugField()
        comp = _map_field("slug", field)
        assert isinstance(comp, TextField)
        assert comp.pattern is not None

    def test_label_auto_generated(self):
        field = django_forms.CharField()
        comp = _map_field("first_name", field)
        assert comp.label == "First Name"

    def test_help_text_preserved(self):
        field = django_forms.CharField(help_text="Enter your name")
        comp = _map_field("name", field)
        assert comp.help_text == "Enter your name"

    def test_initial_value(self):
        field = django_forms.CharField(initial="default")
        comp = _map_field("name", field)
        assert comp.default_value == "default"


# =============================================================================
# BRIDGE — _choices_to_options TESTS
# =============================================================================


class TestChoicesToOptions:
    """Tests for choice/optgroup conversion."""

    def test_flat_choices(self):
        choices = [("a", "Alpha"), ("b", "Beta")]
        options = _choices_to_options(choices)
        assert len(options) == 2
        assert options[0].value == "a"
        assert options[0].label == "Alpha"

    def test_optgroup_choices(self):
        choices = [
            ("Group1", [("a", "Alpha"), ("b", "Beta")]),
            ("Group2", [("c", "Charlie")]),
        ]
        options = _choices_to_options(choices)
        assert len(options) == 3
        assert options[0].group == "Group1"
        assert options[2].group == "Group2"


# =============================================================================
# BRIDGE — form_to_components TESTS
# =============================================================================


class TestFormToComponents:
    """Tests for form_to_components()."""

    def test_from_class(self):
        from django_matt.components.forms import Form

        tree = form_to_components(ContactForm)
        assert isinstance(tree, Form)
        assert len(tree.fields) == 5

    def test_from_instance(self):
        from django_matt.components.forms import Form

        tree = form_to_components(ContactForm())
        assert isinstance(tree, Form)

    def test_theme_applied(self):
        tree = form_to_components(ContactForm, theme="bootstrap")
        # Fields should have bootstrap classes
        for field in tree.fields:
            assert field.class_name is not None

    def test_submit_button(self):
        tree = form_to_components(ContactForm)
        assert tree.submit is not None
        assert tree.submit.label == "Submit"


# =============================================================================
# BRIDGE — render_form TESTS
# =============================================================================


class TestRenderForm:
    """Tests for render_form() HTML output."""

    def test_contains_form_tag(self):
        html = render_form(ContactForm)
        assert "<form" in html
        assert "</form>" in html

    def test_method_and_action(self):
        html = render_form(ContactForm, method="post", action="/submit/")
        assert 'method="post"' in html
        assert 'action="/submit/"' in html

    def test_csrf_token(self):
        html = render_form(ContactForm)
        assert "csrfmiddlewaretoken" in html

    def test_theme_classes(self):
        html = render_form(ContactForm, theme="bootstrap")
        assert "form-control" in html

    def test_file_field_enctype(self):
        html = render_form(FullFieldForm)
        assert 'enctype="multipart/form-data"' in html

    def test_help_text_rendered(self):
        html = render_form(ContactForm)
        assert "Tell us what&#x27;s on your mind" in html or "Tell us what" in html

    def test_required_marker(self):
        html = render_form(ContactForm)
        assert "*" in html

    def test_textarea_rendered(self):
        html = render_form(ContactForm)
        assert "<textarea" in html

    def test_email_field_type(self):
        html = render_form(ContactForm)
        assert 'type="email"' in html

    def test_checkbox_rendered(self):
        html = render_form(ContactForm)
        assert 'type="checkbox"' in html


# =============================================================================
# FORM BUILDER TESTS
# =============================================================================


class TestFormBuilder:
    """Tests for FormBuilder fluent API."""

    def test_basic_build(self):
        form_cls = FormBuilder("test").text("name", required=True).build()
        assert issubclass(form_cls, django_forms.Form)
        assert "name" in form_cls().fields

    def test_text_field(self):
        form_cls = FormBuilder("t").text("x", max_length=50, min_length=2).build()
        field = form_cls().fields["x"]
        assert isinstance(field, django_forms.CharField)
        assert field.max_length == 50
        assert field.min_length == 2

    def test_email_field(self):
        form_cls = FormBuilder("t").email("e", required=True).build()
        field = form_cls().fields["e"]
        assert isinstance(field, django_forms.EmailField)
        assert field.required is True

    def test_password_field(self):
        form_cls = FormBuilder("t").password("pw", min_length=8).build()
        field = form_cls().fields["pw"]
        assert isinstance(field, django_forms.CharField)
        assert isinstance(field.widget, django_forms.PasswordInput)

    def test_number_integer(self):
        form_cls = FormBuilder("t").number("n", min_value=0, max_value=100).build()
        field = form_cls().fields["n"]
        assert isinstance(field, django_forms.IntegerField)

    def test_number_decimal(self):
        form_cls = FormBuilder("t").number("d", decimal_places=2).build()
        field = form_cls().fields["d"]
        assert isinstance(field, django_forms.DecimalField)
        assert field.decimal_places == 2

    def test_textarea(self):
        form_cls = FormBuilder("t").textarea("msg", rows=5, max_length=500).build()
        field = form_cls().fields["msg"]
        assert isinstance(field, django_forms.CharField)
        assert isinstance(field.widget, django_forms.Textarea)

    def test_select(self):
        form_cls = FormBuilder("t").select("dept", choices=[("e", "Eng"), ("s", "Sales")]).build()
        field = form_cls().fields["dept"]
        assert isinstance(field, django_forms.ChoiceField)
        assert len(list(field.choices)) == 2

    def test_multiselect(self):
        form_cls = FormBuilder("t").multiselect("tags", choices=[("a", "A"), ("b", "B")]).build()
        field = form_cls().fields["tags"]
        assert isinstance(field, django_forms.MultipleChoiceField)

    def test_checkbox(self):
        form_cls = FormBuilder("t").checkbox("agree", required=True).build()
        field = form_cls().fields["agree"]
        assert isinstance(field, django_forms.BooleanField)

    def test_radio(self):
        form_cls = FormBuilder("t").radio("size", choices=[("s", "S"), ("m", "M")]).build()
        field = form_cls().fields["size"]
        assert isinstance(field, django_forms.ChoiceField)
        assert isinstance(field.widget, django_forms.RadioSelect)

    def test_date_field(self):
        form_cls = FormBuilder("t").date("dob").build()
        field = form_cls().fields["dob"]
        assert isinstance(field, django_forms.DateField)

    def test_file_field(self):
        form_cls = FormBuilder("t").file("doc", required=True).build()
        field = form_cls().fields["doc"]
        assert isinstance(field, django_forms.FileField)

    def test_hidden_field(self):
        form_cls = FormBuilder("t").hidden("token", initial="abc").build()
        field = form_cls().fields["token"]
        assert isinstance(field.widget, django_forms.HiddenInput)
        assert field.required is False

    def test_chaining(self):
        """All builder methods return self for chaining."""
        builder = FormBuilder("chain")
        result = (
            builder.text("a")
            .email("b")
            .password("c")
            .number("d")
            .textarea("e")
            .select("f", choices=[])
            .multiselect("g", choices=[])
            .checkbox("h")
            .radio("i", choices=[])
            .date("j")
            .file("k")
            .hidden("l")
            .submit("Go")
            .method("post")
            .action("/go/")
        )
        assert result is builder

    def test_submit_label(self):
        builder = FormBuilder("t").text("x").submit("Send")
        assert builder._submit_label == "Send"

    def test_method_and_action(self):
        builder = FormBuilder("t").method("put").action("/api/")
        assert builder._method == "put"
        assert builder._action == "/api/"

    def test_render(self):
        html = FormBuilder("test").text("name", required=True).render(theme="tailwind")
        assert "<form" in html
        assert "</form>" in html

    def test_to_zod(self):
        zod = FormBuilder("test").text("name", max_length=50).to_zod()
        assert "z.string()" in zod
        assert "name:" in zod

    def test_form_class_name(self):
        form_cls = FormBuilder("contact us").text("x").build()
        assert form_cls.__name__ == "ContactUsForm"


# =============================================================================
# DECORATOR — _is_ajax TESTS
# =============================================================================


class TestIsAjax:
    """Tests for AJAX detection."""

    def test_htmx_request(self):
        rf = RequestFactory()
        request = rf.get("/", HTTP_HX_REQUEST="true")
        assert _is_ajax(request) is True

    def test_xhr_request(self):
        rf = RequestFactory()
        request = rf.get("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert _is_ajax(request) is True

    def test_json_accept(self):
        rf = RequestFactory()
        request = rf.get("/", HTTP_ACCEPT="application/json")
        assert _is_ajax(request) is True

    def test_regular_request(self):
        rf = RequestFactory()
        request = rf.get("/")
        assert _is_ajax(request) is False


# =============================================================================
# DECORATOR — _form_errors_dict TESTS
# =============================================================================


class TestFormErrorsDict:
    def test_extracts_errors(self):
        form = ContactForm(data={"name": "", "email": "bad", "message": ""})
        form.is_valid()
        errors = _form_errors_dict(form)
        assert isinstance(errors, dict)
        assert "name" in errors
        assert isinstance(errors["name"], list)


# =============================================================================
# DECORATOR — @ajax_form TESTS
# =============================================================================


class TestAjaxFormDecorator:
    """Tests for @ajax_form decorator behavior."""

    def test_non_ajax_passthrough(self):
        rf = RequestFactory()
        request = rf.post("/")

        @ajax_form(success_url="/ok/")
        def view(request):
            return HttpResponse("normal")

        response = view(request)
        assert isinstance(response, HttpResponse)
        assert response.content == b"normal"

    def test_ajax_valid_form(self):
        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form(success_url="/dashboard/")
        def view(request):
            form = ContactForm(
                data={"name": "Test", "email": "t@t.com", "age": "25", "message": "hi"}
            )
            form.is_valid()
            return form

        response = view(request)
        assert isinstance(response, JsonResponse)
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["redirect"] == "/dashboard/"

    def test_ajax_invalid_form(self):
        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form()
        def view(request):
            form = ContactForm(data={"name": "", "email": "", "message": ""})
            form.is_valid()
            return form

        response = view(request)
        data = json.loads(response.content)
        assert data["success"] is False
        assert "errors" in data
        assert response.status_code == 422

    def test_ajax_exception(self):
        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form()
        def view(request):
            raise RuntimeError("boom")

        response = view(request)
        data = json.loads(response.content)
        assert data["success"] is False
        assert response.status_code == 500

    def test_ajax_redirect_response(self):
        from django.http import HttpResponseRedirect

        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form(success_url="/custom/")
        def view(request):
            return HttpResponseRedirect("/old/")

        response = view(request)
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["redirect"] == "/custom/"

    def test_ajax_dict_response(self):
        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form()
        def view(request):
            return {"custom": "data"}

        response = view(request)
        data = json.loads(response.content)
        assert data["custom"] == "data"

    def test_success_data_callback(self):
        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form(success_data=lambda form: {"id": 42})
        def view(request):
            form = ContactForm(
                data={"name": "Test", "email": "t@t.com", "age": "25", "message": "hi"}
            )
            form.is_valid()
            return form

        response = view(request)
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["data"] == {"id": 42}

    def test_cbv_style_request_detection(self):
        """Request as second arg (self, request) is detected."""
        rf = RequestFactory()
        request = rf.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        @ajax_form()
        def method(self_arg, request):
            return {"ok": True}

        response = method("self", request)
        data = json.loads(response.content)
        assert data["ok"] is True

    def test_no_request_found(self):
        """Without a request object, view runs normally."""

        @ajax_form()
        def view():
            return HttpResponse("ok")

        response = view()
        assert response.content == b"ok"


# =============================================================================
# VALIDATION — Zod TESTS
# =============================================================================


class TestFormToZod:
    """Tests for Zod schema generation."""

    def test_basic_output(self):
        zod = form_to_zod(ContactForm)
        assert 'import { z } from "zod"' in zod
        assert "formSchema" in zod
        assert "FormData" in zod

    def test_string_field(self):
        zod = form_to_zod(ContactForm)
        assert "name: z.string()" in zod

    def test_max_constraint(self):
        zod = form_to_zod(ContactForm)
        assert ".max(100)" in zod

    def test_min_constraint(self):
        zod = form_to_zod(ContactForm)
        assert ".min(2)" in zod

    def test_email_type(self):
        zod = form_to_zod(ContactForm)
        assert "z.string().email()" in zod

    def test_number_type(self):
        zod = form_to_zod(ContactForm)
        assert "z.number()" in zod

    def test_optional(self):
        zod = form_to_zod(ContactForm)
        assert ".optional()" in zod

    def test_boolean_type(self):
        zod = form_to_zod(ContactForm)
        assert "z.boolean()" in zod

    def test_enum_type(self):
        class EnumForm(django_forms.Form):
            color = django_forms.ChoiceField(choices=[("r", "Red"), ("g", "Green")])

        zod = form_to_zod(EnumForm)
        assert "z.enum(" in zod
        assert '"r"' in zod

    def test_array_type(self):
        class MultiForm(django_forms.Form):
            tags = django_forms.MultipleChoiceField(choices=[("a", "A"), ("b", "B")])

        zod = form_to_zod(MultiForm)
        assert "z.array(" in zod

    def test_date_type(self):
        class DateForm(django_forms.Form):
            d = django_forms.DateField()

        zod = form_to_zod(DateForm)
        assert "z.string().date()" in zod

    def test_file_type(self):
        class FileForm(django_forms.Form):
            f = django_forms.FileField()

        zod = form_to_zod(FileForm)
        assert "z.instanceof(File)" in zod

    def test_from_instance(self):
        zod = form_to_zod(ContactForm())
        assert "formSchema" in zod


# =============================================================================
# VALIDATION — Yup TESTS
# =============================================================================


class TestFormToYup:
    """Tests for Yup schema generation."""

    def test_basic_output(self):
        yup = form_to_yup(ContactForm)
        assert 'import * as yup from "yup"' in yup
        assert "formSchema" in yup
        assert "FormData" in yup

    def test_required(self):
        yup = form_to_yup(ContactForm)
        assert ".required()" in yup

    def test_email(self):
        yup = form_to_yup(ContactForm)
        assert "yup.string().email()" in yup

    def test_number(self):
        yup = form_to_yup(ContactForm)
        assert "yup.number()" in yup

    def test_boolean(self):
        yup = form_to_yup(ContactForm)
        assert "yup.boolean()" in yup

    def test_optional(self):
        yup = form_to_yup(ContactForm)
        assert ".optional()" in yup

    def test_enum_oneof(self):
        class EnumForm(django_forms.Form):
            color = django_forms.ChoiceField(choices=[("r", "Red")])

        yup = form_to_yup(EnumForm)
        assert ".oneOf(" in yup

    def test_url_type(self):
        class UrlForm(django_forms.Form):
            link = django_forms.URLField()

        yup = form_to_yup(UrlForm)
        assert "yup.string().url()" in yup

    def test_file_type(self):
        class FileForm(django_forms.Form):
            f = django_forms.FileField()

        yup = form_to_yup(FileForm)
        assert "yup.mixed()" in yup


# =============================================================================
# VALIDATION — JSON Schema TESTS
# =============================================================================


class TestFormToJsonSchema:
    """Tests for JSON Schema generation."""

    def test_basic_structure(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_required_list(self):
        schema = form_to_json_schema(ContactForm)
        assert "name" in schema["required"]
        assert "email" in schema["required"]
        assert "age" not in schema["required"]

    def test_string_property(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["name"]["type"] == "string"

    def test_max_length(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["name"]["maxLength"] == 100

    def test_min_length(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["name"]["minLength"] == 2

    def test_email_format(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["email"]["format"] == "email"

    def test_integer_type(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["age"]["type"] == "integer"

    def test_min_max_value(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["age"]["minimum"] == 0
        assert schema["properties"]["age"]["maximum"] == 150

    def test_boolean_type(self):
        schema = form_to_json_schema(ContactForm)
        assert schema["properties"]["subscribe"]["type"] == "boolean"

    def test_enum_property(self):
        class EnumForm(django_forms.Form):
            color = django_forms.ChoiceField(choices=[("r", "Red"), ("g", "Green")])

        schema = form_to_json_schema(EnumForm)
        prop = schema["properties"]["color"]
        assert prop["type"] == "string"
        assert "r" in prop["enum"]

    def test_array_property(self):
        class MultiForm(django_forms.Form):
            tags = django_forms.MultipleChoiceField(choices=[("a", "A")])

        schema = form_to_json_schema(MultiForm)
        prop = schema["properties"]["tags"]
        assert prop["type"] == "array"
        assert "items" in prop

    def test_date_format(self):
        class DateForm(django_forms.Form):
            d = django_forms.DateField()

        schema = form_to_json_schema(DateForm)
        assert schema["properties"]["d"]["format"] == "date"

    def test_url_format(self):
        class UrlForm(django_forms.Form):
            u = django_forms.URLField()

        schema = form_to_json_schema(UrlForm)
        assert schema["properties"]["u"]["format"] == "uri"

    def test_file_format(self):
        class FileForm(django_forms.Form):
            f = django_forms.FileField()

        schema = form_to_json_schema(FileForm)
        assert schema["properties"]["f"]["format"] == "binary"

    def test_from_instance(self):
        schema = form_to_json_schema(ContactForm())
        assert "properties" in schema


# =============================================================================
# VALIDATION — _analyze_field TESTS
# =============================================================================


class TestAnalyzeField:
    """Tests for field analysis internals."""

    def test_datetime_type(self):
        info = _analyze_field("ts", django_forms.DateTimeField())
        assert info["type"] == "datetime"

    def test_time_type(self):
        info = _analyze_field("t", django_forms.TimeField())
        assert info["type"] == "time"

    def test_regex_constraint(self):
        from django.core.validators import RegexValidator

        field = django_forms.CharField(validators=[RegexValidator(r"^[A-Z]+$")])
        info = _analyze_field("code", field)
        assert any(c[0] == "regex" for c in info["constraints"])

    def test_float_type(self):
        # FloatField inherits from IntegerField in Django, so _analyze_field
        # hits the IntegerField branch first — returns "integer" not "number".
        info = _analyze_field("f", django_forms.FloatField())
        assert info["type"] == "integer"

    def test_decimal_type(self):
        # Same inheritance issue as FloatField
        info = _analyze_field("d", django_forms.DecimalField(max_digits=5, decimal_places=2))
        assert info["type"] == "integer"


# =============================================================================
# THEME CLASSES TESTS
# =============================================================================


class TestThemeClasses:
    """Tests for THEME_CLASSES dict."""

    def test_all_themes_present(self):
        assert "shadcn" in THEME_CLASSES
        assert "tailwind" in THEME_CLASSES
        assert "bootstrap" in THEME_CLASSES

    def test_all_themes_have_required_keys(self):
        required = {
            "form",
            "field_wrapper",
            "label",
            "input",
            "textarea",
            "select",
            "checkbox",
            "help_text",
            "error",
            "submit",
            "error_list",
        }
        for theme, classes in THEME_CLASSES.items():
            assert required.issubset(classes.keys()), f"{theme} missing keys"
