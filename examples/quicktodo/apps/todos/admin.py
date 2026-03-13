from django.contrib import admin

from .models import Todo, TodoList


@admin.register(TodoList)
class TodoListAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_by", "created_at")
    list_filter = ("organization",)
    search_fields = ("name",)


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ("title", "todo_list", "status", "priority", "assignee", "due_date")
    list_filter = ("status", "priority")
    search_fields = ("title", "description")
