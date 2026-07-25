"""Controllers for {{ project_name }}."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django_matt.auth import jwt_required

from .models import Item
from .schemas import ItemCreate, ItemSchema, ItemUpdate


async def health(request) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
@jwt_required
async def list_items(request) -> JsonResponse:
    items = [
        ItemSchema.model_validate(item)
        async for item in Item.objects.all()
    ]
    return JsonResponse({"items": [i.model_dump(mode="json") for i in items]})


@require_http_methods(["POST"])
@jwt_required
async def create_item(request) -> JsonResponse:
    import orjson

    data = ItemCreate.model_validate(orjson.loads(request.body))
    item = await Item.objects.acreate(title=data.title, description=data.description)
    return JsonResponse(
        ItemSchema.model_validate(item).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["GET"])
@jwt_required
async def get_item(request, item_id: int) -> JsonResponse:
    try:
        item = await Item.objects.aget(pk=item_id)
    except Item.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse(ItemSchema.model_validate(item).model_dump(mode="json"))


@require_http_methods(["PATCH"])
@jwt_required
async def update_item(request, item_id: int) -> JsonResponse:
    import orjson

    try:
        item = await Item.objects.aget(pk=item_id)
    except Item.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    data = ItemUpdate.model_validate(orjson.loads(request.body))
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await item.asave()
    return JsonResponse(ItemSchema.model_validate(item).model_dump(mode="json"))


@require_http_methods(["DELETE"])
@jwt_required
async def delete_item(request, item_id: int) -> JsonResponse:
    try:
        item = await Item.objects.aget(pk=item_id)
    except Item.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    await item.adelete()
    return JsonResponse({"deleted": True})
