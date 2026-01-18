"""
Management command for messaging operations.

Usage:
    python manage.py messaging cleanup --days 90
    python manage.py messaging stats
    python manage.py messaging export --conversation 123 --output messages.json
    python manage.py messaging purge-deleted --dry-run
"""

import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, Max, Min
from django.utils import timezone


class Command(BaseCommand):
    """Management command for messaging operations."""

    help = "Messaging system management operations"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

        # cleanup subcommand
        cleanup_parser = subparsers.add_parser(
            "cleanup",
            help="Clean up old messages and attachments",
        )
        cleanup_parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Delete messages older than this many days",
        )
        cleanup_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without deleting",
        )
        cleanup_parser.add_argument(
            "--include-attachments",
            action="store_true",
            help="Also delete attachment files from storage",
        )

        # stats subcommand
        subparsers.add_parser(
            "stats",
            help="Show messaging statistics",
        )

        # export subcommand
        export_parser = subparsers.add_parser(
            "export",
            help="Export conversation messages to JSON",
        )
        export_parser.add_argument(
            "--conversation",
            type=int,
            required=True,
            help="Conversation ID to export",
        )
        export_parser.add_argument(
            "--output",
            "-o",
            required=True,
            help="Output file path",
        )
        export_parser.add_argument(
            "--include-deleted",
            action="store_true",
            help="Include soft-deleted messages",
        )

        # purge-deleted subcommand
        purge_parser = subparsers.add_parser(
            "purge-deleted",
            help="Permanently delete soft-deleted messages",
        )
        purge_parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Purge messages deleted more than this many days ago",
        )
        purge_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be purged without purging",
        )

        # clear-presence subcommand
        subparsers.add_parser(
            "clear-presence",
            help="Clear all presence and typing indicators from cache",
        )

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")

        if not subcommand:
            self.print_help("manage.py", "messaging")
            return

        handler = getattr(self, f"handle_{subcommand.replace('-', '_')}", None)
        if handler:
            handler(options)
        else:
            raise CommandError(f"Unknown subcommand: {subcommand}")

    def handle_cleanup(self, options):
        """Clean up old messages."""
        from django_matt.messaging.models import Attachment, Message

        days = options["days"]
        dry_run = options["dry_run"]
        include_attachments = options["include_attachments"]

        cutoff_date = timezone.now() - timedelta(days=days)

        # Find old messages
        old_messages = Message.objects.filter(created_at__lt=cutoff_date)
        message_count = old_messages.count()

        # Find attachments
        attachment_count = 0
        if include_attachments:
            attachment_count = Attachment.objects.filter(
                message__created_at__lt=cutoff_date
            ).count()

        if dry_run:
            self.stdout.write(
                f"Would delete {message_count} messages older than {days} days"
            )
            if include_attachments:
                self.stdout.write(f"Would delete {attachment_count} attachments")
        else:
            if include_attachments:
                # Delete attachment files first
                attachments = Attachment.objects.filter(message__created_at__lt=cutoff_date)
                for attachment in attachments:
                    attachment.delete_file()
                attachments.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted {attachment_count} attachments")
                )

            # Delete messages (cascades to statuses, reactions, etc.)
            old_messages.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {message_count} messages older than {days} days"
                )
            )

    def handle_stats(self, options):
        """Show messaging statistics."""
        from django_matt.messaging.models import (
            Attachment,
            Conversation,
            ConversationMember,
            Message,
            MessageReaction,
        )

        # Conversation stats
        conv_stats = Conversation.objects.aggregate(
            total=Count("id"),
            direct=Count("id", filter=Count("conversation_type") == "direct"),
            archived=Count("id", filter=Count("is_archived") == True),  # noqa: E712
        )

        # Message stats
        msg_stats = Message.objects.aggregate(
            total=Count("id"),
            deleted=Count("id", filter=Count("is_deleted") == True),  # noqa: E712
            pinned=Count("id", filter=Count("is_pinned") == True),  # noqa: E712
            edited=Count("id", filter=Count("is_edited") == True),  # noqa: E712
            oldest=Min("created_at"),
            newest=Max("created_at"),
        )

        # Member stats
        member_stats = ConversationMember.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Count("is_active") == True),  # noqa: E712
        )

        # Messages per conversation
        messages_per_conv = Conversation.objects.annotate(
            msg_count=Count("messages")
        ).aggregate(
            avg=Avg("msg_count"),
            max=Max("msg_count"),
        )

        # Attachment stats
        attachment_stats = Attachment.objects.aggregate(
            total=Count("id"),
        )

        # Reaction stats
        reaction_stats = MessageReaction.objects.aggregate(
            total=Count("id"),
        )

        self.stdout.write("\n=== Messaging Statistics ===\n")

        self.stdout.write("Conversations:")
        self.stdout.write(f"  Total: {conv_stats['total']}")
        self.stdout.write(f"  Archived: {conv_stats['archived']}")

        self.stdout.write("\nMessages:")
        self.stdout.write(f"  Total: {msg_stats['total']}")
        self.stdout.write(f"  Deleted: {msg_stats['deleted']}")
        self.stdout.write(f"  Pinned: {msg_stats['pinned']}")
        self.stdout.write(f"  Edited: {msg_stats['edited']}")
        if msg_stats["oldest"]:
            self.stdout.write(f"  Oldest: {msg_stats['oldest']}")
        if msg_stats["newest"]:
            self.stdout.write(f"  Newest: {msg_stats['newest']}")

        self.stdout.write("\nMembers:")
        self.stdout.write(f"  Total: {member_stats['total']}")
        self.stdout.write(f"  Active: {member_stats['active']}")

        self.stdout.write("\nPer Conversation:")
        self.stdout.write(f"  Avg messages: {messages_per_conv['avg']:.1f}" if messages_per_conv['avg'] else "  Avg messages: 0")
        self.stdout.write(f"  Max messages: {messages_per_conv['max'] or 0}")

        self.stdout.write("\nAttachments:")
        self.stdout.write(f"  Total: {attachment_stats['total']}")

        self.stdout.write("\nReactions:")
        self.stdout.write(f"  Total: {reaction_stats['total']}")

        self.stdout.write("")

    def handle_export(self, options):
        """Export conversation to JSON."""
        from django_matt.messaging.models import Conversation, Message

        conversation_id = options["conversation"]
        output_path = options["output"]
        include_deleted = options["include_deleted"]

        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            raise CommandError(f"Conversation {conversation_id} not found")

        # Get messages
        messages_qs = Message.objects.filter(conversation=conversation)
        if not include_deleted:
            messages_qs = messages_qs.filter(is_deleted=False)

        messages_qs = messages_qs.select_related("sender").prefetch_related(
            "attachments", "reactions"
        ).order_by("created_at")

        # Build export data
        export_data = {
            "conversation": {
                "id": conversation.id,
                "name": conversation.name,
                "type": conversation.conversation_type,
                "created_at": conversation.created_at.isoformat(),
            },
            "members": [
                {
                    "user_id": m.user_id,
                    "role": m.role,
                    "joined_at": m.joined_at.isoformat(),
                }
                for m in conversation.get_members()
            ],
            "messages": [
                {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "created_at": msg.created_at.isoformat(),
                    "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
                    "is_deleted": msg.is_deleted,
                    "is_pinned": msg.is_pinned,
                    "attachments": [
                        {
                            "filename": a.original_filename,
                            "content_type": a.content_type,
                            "file_size": a.file_size,
                        }
                        for a in msg.attachments.all()
                    ],
                    "reactions": list(msg.get_reactions_summary()),
                }
                for msg in messages_qs
            ],
            "exported_at": timezone.now().isoformat(),
        }

        # Write to file
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(export_data['messages'])} messages to {output_path}"
            )
        )

    def handle_purge_deleted(self, options):
        """Permanently delete soft-deleted messages."""
        from django_matt.messaging.models import Message

        days = options["days"]
        dry_run = options["dry_run"]

        cutoff_date = timezone.now() - timedelta(days=days)

        # Find old soft-deleted messages
        deleted_messages = Message.objects.filter(
            is_deleted=True,
            deleted_at__lt=cutoff_date,
        )
        count = deleted_messages.count()

        if dry_run:
            self.stdout.write(
                f"Would permanently delete {count} soft-deleted messages "
                f"(deleted more than {days} days ago)"
            )
        else:
            # Delete attachments first
            from django_matt.messaging.models import Attachment

            attachments = Attachment.objects.filter(message__in=deleted_messages)
            for attachment in attachments:
                attachment.delete_file()

            # Permanently delete messages
            deleted_messages.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Permanently deleted {count} soft-deleted messages"
                )
            )

    def handle_clear_presence(self, options):
        """Clear all presence data from cache."""
        from django.core.cache import cache

        from django_matt.messaging.services import PresenceService

        # Clear all presence-related cache keys
        # Note: This is a simplified approach. For production, you might need
        # to iterate through known keys or use a cache backend that supports
        # pattern deletion.
        patterns = [
            PresenceService.ONLINE_PREFIX,
            PresenceService.TYPING_PREFIX,
            PresenceService.LAST_SEEN_PREFIX,
        ]

        self.stdout.write("Clearing presence cache...")
        self.stdout.write(
            self.style.WARNING(
                "Note: This clears cache keys by pattern. "
                "Some cache backends may not support this operation."
            )
        )

        # Try to clear using cache.delete_pattern if available (Redis)
        if hasattr(cache, "delete_pattern"):
            for pattern in patterns:
                cache.delete_pattern(f"{pattern}*")
                self.stdout.write(f"  Cleared {pattern}*")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Cache backend does not support pattern deletion. "
                    "Presence data will expire naturally."
                )
            )

        self.stdout.write(self.style.SUCCESS("Presence cache cleared"))
