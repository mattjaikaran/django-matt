"""
Unfold Admin integration for the native task engine.

Provides a modern dashboard for task management with:
- Real-time task status
- Failure tracking with stack traces
- Retry/cancel controls
- Schedule management
- Queue metrics
"""

from .dashboard import TaskDashboard, get_task_dashboard_callback, get_task_widgets
from .filters import QueueFilter, StateFilter, TaskNameFilter

__all__ = [
    "TaskDashboard",
    "get_task_dashboard_callback",
    "get_task_widgets",
    "QueueFilter",
    "StateFilter",
    "TaskNameFilter",
    "register_admin",
]


def register_admin(admin_site=None):
    """
    Register task admin classes with Django admin.

    Call this from your AppConfig.ready() or manually after Django is ready.

    Usage:
        # In your apps.py
        from django_matt.tasks_native.admin import register_admin

        class MyAppConfig(AppConfig):
            def ready(self):
                register_admin()

        # Or with custom admin site
        from django.contrib.admin import AdminSite
        my_admin = AdminSite(name='myadmin')
        register_admin(my_admin)
    """
    from django.contrib import admin as django_admin

    from ..models import DeadLetterTask, ScheduleHistory, TaskExecution, TaskSchedule
    from .dead_letter import DeadLetterTaskAdmin
    from .execution import TaskExecutionAdmin
    from .schedule import ScheduleHistoryAdmin, TaskScheduleAdmin

    site = admin_site or django_admin.site

    # Only register if not already registered
    if TaskExecution not in site._registry:
        site.register(TaskExecution, TaskExecutionAdmin)

    if TaskSchedule not in site._registry:
        site.register(TaskSchedule, TaskScheduleAdmin)

    if ScheduleHistory not in site._registry:
        site.register(ScheduleHistory, ScheduleHistoryAdmin)

    if DeadLetterTask not in site._registry:
        site.register(DeadLetterTask, DeadLetterTaskAdmin)
