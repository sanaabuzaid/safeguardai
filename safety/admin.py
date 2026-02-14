from django.contrib import admin
from .models import User, Document, Conversation, SafetyLog


def truncate(field, length=60):
    def truncated(obj):
        value = getattr(obj, field, '') or ''
        return value[:length] + '...' if len(value) > length else value
    truncated.short_description = field.replace('_', ' ').title()
    return truncated


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'role', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['phone_number']
    ordering = ['-created_at']
    list_per_page = 25
    readonly_fields = ['created_at']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'uploaded_by', 'uploaded_at', 'is_active']
    list_filter = ['is_active', 'uploaded_at']
    search_fields = ['title']
    ordering = ['-uploaded_at']
    list_per_page = 25
    readonly_fields = ['uploaded_at', 'updated_at']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['user', truncate('message', 60), truncate('response', 60), 'created_at']
    list_filter = ['created_at']
    search_fields = ['message', 'response']
    ordering = ['-created_at']
    list_per_page = 25
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(SafetyLog)
class SafetyLogAdmin(admin.ModelAdmin):
    list_display = ['user', truncate('task_description', 60), truncate('safety_check', 60), 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['task_description', 'safety_check']
    ordering = ['-timestamp']
    list_per_page = 25
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
