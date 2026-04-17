# Message Attachments

File attachment handling for the messaging system. Supports typed attachments (image, video, audio, document, file) with metadata for dimensions, duration, and thumbnails.

## Quick Start

```python
from django_matt.messaging.schemas import SendMessageSchema, AttachmentSchema

# Send a message with attachment metadata
message = SendMessageSchema(
    content="Check out this document",
    message_type="text",
    metadata={"has_attachments": True},
)

# Attachment schema for API responses
attachment = AttachmentSchema(
    id=1,
    filename="report-2024.pdf",
    original_filename="Q4 Report.pdf",
    content_type="application/pdf",
    attachment_type="document",
    file_size=245760,
    url="/media/attachments/report-2024.pdf",
)
```

## Key Features

### AttachmentSchema

The `AttachmentSchema` represents file attachments in API responses:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Attachment ID |
| `filename` | `str` | Server-side filename |
| `original_filename` | `str` | Original upload filename |
| `content_type` | `str` | MIME type (e.g., `image/png`) |
| `attachment_type` | `str` | Category: `image`, `video`, `audio`, `document`, `file` |
| `file_size` | `int` | Size in bytes |
| `url` | `str` | Download URL |
| `thumbnail_url` | `str` | Thumbnail URL (images/videos) |
| `width` | `int | None` | Width in pixels (images/videos) |
| `height` | `int | None` | Height in pixels (images/videos) |
| `duration` | `int | None` | Duration in seconds (audio/video) |

### Message with Attachments

Messages include attachments in their schema:

```python
from django_matt.messaging.schemas import MessageSchema

# MessageSchema includes:
# - attachments: list[AttachmentSchema] (default empty)
# - reactions: list[MessageReactionSummarySchema]
# - message_type: str (text, image, video, audio, document, system)
```

### Conversation Schemas

The messaging module provides complete conversation management:

```python
from django_matt.messaging.schemas import (
    # Conversations
    ConversationSchema,
    ConversationListSchema,
    ConversationDetailSchema,
    CreateDirectConversationSchema,
    CreateGroupConversationSchema,
    UpdateConversationSchema,
    AddMembersSchema,
    UpdateMemberRoleSchema,
    ConversationSettingsSchema,

    # Messages
    MessageSchema,
    MessageDetailSchema,
    SendMessageSchema,
    EditMessageSchema,

    # Reactions
    ReactionSchema,
    MessageReactionSchema,

    # Delivery
    MessageStatusSchema,
    ReadReceiptSchema,

    # Presence
    TypingIndicatorSchema,
    PresenceSchema,

    # Search
    SearchMessagesSchema,
    SearchResultSchema,
    PaginatedMessagesSchema,
)
```

### Message Types

Messages support multiple types via the `message_type` field:

- `text` -- Plain text message
- `image` -- Image attachment
- `video` -- Video attachment
- `audio` -- Audio attachment
- `document` -- Document attachment
- `system` -- System-generated message

## Practical Example

A view that handles file upload and creates an attachment:

```python
from django_matt.messaging.schemas import (
    SendMessageSchema,
    AttachmentSchema,
    MessageSchema,
)

async def send_message_with_attachment(request, conversation_id: int):
    data = SendMessageSchema(
        content=request.POST.get("content", ""),
        message_type="document",
    )

    # Process uploaded file (using django_matt.files for storage)
    uploaded = request.FILES.get("file")
    if uploaded:
        attachment = AttachmentSchema(
            id=1,
            filename=uploaded.name,
            original_filename=uploaded.name,
            content_type=uploaded.content_type,
            attachment_type=_detect_type(uploaded.content_type),
            file_size=uploaded.size,
            url=f"/media/conversations/{conversation_id}/{uploaded.name}",
        )
        # Save file and create message with attachment reference

    return {"status": "sent"}


def _detect_type(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    if content_type in ("application/pdf", "application/msword"):
        return "document"
    return "file"
```
