import inspect
import json
from functools import wraps
from typing import Any, Dict, List, get_type_hints

from django.http import HttpRequest, JsonResponse
from pydantic import BaseModel, ValidationError


class Controller:
	"""
	Base controller class for Django Matt framework.

	Controllers provide a class-based approach to defining API endpoints.
	Methods can be decorated with route decorators to define endpoints.
	"""

	prefix: str = ''
	tags: List[str] = []

	def __init__(self):
		self._setup_dependencies()

	def _setup_dependencies(self):
		"""
		Set up dependencies for controller methods based on type hints.
		This allows for automatic dependency injection in controller methods.
		"""
		for method_name in dir(self):
			if method_name.startswith('_'):
				continue

			method = getattr(self, method_name)
			if not callable(method) or not hasattr(method, '_route_info'):
				continue

			# Get type hints for the method
			hints = get_type_hints(method)

			# Create a wrapper that injects dependencies
			@wraps(method)
			async def wrapper(request, *args, **kwargs):
				# Process request body if it exists
				body_data = {}
				if request.body and request.content_type == 'application/json':
					try:
						body_data = json.loads(request.body)
					except json.JSONDecodeError:
						return JsonResponse({'detail': 'Invalid JSON'}, status=400)

				# Inject dependencies based on type hints
				for param_name, param_type in hints.items():
					if param_name == 'return':
						continue

					if param_name == 'request':
						kwargs[param_name] = request
						continue

					# Check if the parameter is a Pydantic model
					if inspect.isclass(param_type) and issubclass(
						param_type, BaseModel
					):
						try:
							# Try to create the model from body data
							model_instance = param_type(**body_data)
							kwargs[param_name] = model_instance
						except ValidationError as e:
							return JsonResponse(
								{'detail': 'Validation error', 'errors': e.errors()},
								status=422,
							)

				# Call the original method
				if inspect.iscoroutinefunction(method):
					result = await method(*args, **kwargs)
				else:
					result = method(*args, **kwargs)

				return result

			# Replace the original method with the wrapper
			setattr(self, method_name, wrapper)


class APIController(Controller):
	"""
	Controller specifically for API endpoints.
	Provides additional functionality for API-specific concerns.
	"""

	def handle_exception(self, exc: Exception) -> Dict[str, Any]:
		"""
		Handle exceptions raised during request processing.
		Override this method to customize exception handling.
		"""
		if isinstance(exc, ValidationError):
			return {'detail': 'Validation error', 'errors': exc.errors()}, 422

		return {'detail': str(exc)}, 500


class CRUDController(APIController):
	"""
	Base controller for CRUD operations.
	Provides common CRUD methods that can be customized by subclasses.
	"""

	model = None
	schema = None
	create_schema = None
	update_schema = None

	async def list(self, request: HttpRequest) -> Dict[str, Any]:
		"""List all instances of the model."""
		if not self.model:
			raise NotImplementedError('Model not specified')

		queryset = self.model.objects.all()

		# Apply filters from query parameters
		for key, value in request.GET.items():
			if key in self.model._meta.fields:
				queryset = queryset.filter(**{key: value})

		# Convert to list of dictionaries
		items = [self._model_to_dict(item) for item in queryset]

		return {'items': items, 'count': len(items)}

	async def retrieve(self, request: HttpRequest, id: str) -> Dict[str, Any]:
		"""Retrieve a single instance of the model by ID."""
		if not self.model:
			raise NotImplementedError('Model not specified')

		try:
			instance = self.model.objects.get(id=id)
			return self._model_to_dict(instance)
		except self.model.DoesNotExist:
			return JsonResponse(
				{'detail': f'{self.model.__name__} not found'}, status=404
			)

	async def create(self, request: HttpRequest, data: BaseModel) -> Dict[str, Any]:
		"""Create a new instance of the model."""
		if not self.model:
			raise NotImplementedError('Model not specified')

		# Convert Pydantic model to dictionary
		data_dict = data.model_dump()

		# Create the instance
		instance = self.model.objects.create(**data_dict)

		return self._model_to_dict(instance)

	async def update(
		self, request: HttpRequest, id: str, data: BaseModel
	) -> Dict[str, Any]:
		"""Update an existing instance of the model."""
		if not self.model:
			raise NotImplementedError('Model not specified')

		try:
			instance = self.model.objects.get(id=id)

			# Convert Pydantic model to dictionary
			data_dict = data.model_dump()

			# Update the instance
			for key, value in data_dict.items():
				setattr(instance, key, value)

			instance.save()

			return self._model_to_dict(instance)
		except self.model.DoesNotExist:
			return JsonResponse(
				{'detail': f'{self.model.__name__} not found'}, status=404
			)

	async def delete(self, request: HttpRequest, id: str) -> Dict[str, Any]:
		"""Delete an instance of the model."""
		if not self.model:
			raise NotImplementedError('Model not specified')

		try:
			instance = self.model.objects.get(id=id)
			instance.delete()
			return {}
		except self.model.DoesNotExist:
			return JsonResponse(
				{'detail': f'{self.model.__name__} not found'}, status=404
			)

	def _model_to_dict(self, instance) -> Dict[str, Any]:
		"""Convert a model instance to a dictionary."""
		if self.schema:
			# Use the schema to convert the model to a dictionary
			return self.schema.from_orm(instance).model_dump()

		# Fallback to a simple conversion
		result = {}
		for field in instance._meta.fields:
			result[field.name] = getattr(instance, field.name)
		return result
