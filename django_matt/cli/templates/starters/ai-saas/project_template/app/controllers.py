"""Controllers for {{ project_name }}."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django_matt.auth import jwt_required

from .models import Conversation, Document, Message
from .schemas import (
    ConversationCreate,
    ConversationSchema,
    DocumentCreate,
    DocumentSchema,
    MessageCreate,
    MessageSchema,
)


async def health(request) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
@jwt_required
async def list_conversations(request) -> JsonResponse:
    convos = [
        ConversationSchema.model_validate(c).model_dump(mode="json")
        async for c in Conversation.objects.filter(user=request.user)
    ]
    return JsonResponse({"conversations": convos})


@require_http_methods(["POST"])
@jwt_required
async def create_conversation(request) -> JsonResponse:
    import orjson

    data = ConversationCreate.model_validate(orjson.loads(request.body))
    convo = await Conversation.objects.acreate(
        user=request.user,
        title=data.title,
        model=data.model,
    )
    return JsonResponse(
        ConversationSchema.model_validate(convo).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["POST"])
@jwt_required
async def send_message(request, conversation_id: int) -> JsonResponse:
    """Send a message and get AI response (non-streaming)."""
    import orjson

    try:
        convo = await Conversation.objects.aget(pk=conversation_id, user=request.user)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    data = MessageCreate.model_validate(orjson.loads(request.body))

    # Save user message
    user_msg = await Message.objects.acreate(
        conversation=convo,
        role=Message.Role.USER,
        content=data.content,
    )

    # TODO: integrate with django_matt.ai for LLM completion
    # For now, return a stub response
    assistant_msg = await Message.objects.acreate(
        conversation=convo,
        role=Message.Role.ASSISTANT,
        content="AI response placeholder — configure DJANGO_MATT_AI to enable",
    )

    return JsonResponse({
        "user_message": MessageSchema.model_validate(user_msg).model_dump(mode="json"),
        "assistant_message": MessageSchema.model_validate(assistant_msg).model_dump(mode="json"),
    })


@require_http_methods(["POST"])
@jwt_required
async def upload_document(request) -> JsonResponse:
    """Upload a document for RAG indexing."""
    import orjson

    data = DocumentCreate.model_validate(orjson.loads(request.body))
    doc = await Document.objects.acreate(
        user=request.user,
        title=data.title,
        content=data.content,
        metadata=data.metadata,
    )

    # TODO: trigger embedding via django_matt.ml / background task
    return JsonResponse(
        DocumentSchema.model_validate(doc).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["GET"])
@jwt_required
async def list_documents(request) -> JsonResponse:
    docs = [
        DocumentSchema.model_validate(d).model_dump(mode="json")
        async for d in Document.objects.filter(user=request.user)
    ]
    return JsonResponse({"documents": docs})
