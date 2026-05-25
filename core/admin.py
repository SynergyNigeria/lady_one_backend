from django.contrib import admin
from .models import Visitor, Subscriber, Conversation, ChatMessage, SessionLog


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'visit_count', 'first_seen', 'last_seen', 'is_banned']
    list_filter = ['is_banned']
    search_fields = ['ip_address']
    readonly_fields = ['first_seen', 'last_seen', 'visit_count']
    actions = ['ban_visitors', 'unban_visitors']

    @admin.action(description='Ban selected visitors')
    def ban_visitors(self, request, queryset):
        queryset.update(is_banned=True)

    @admin.action(description='Unban selected visitors')
    def unban_visitors(self, request, queryset):
        queryset.update(is_banned=False)


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subscriber_code', 'is_active', 'created_at', 'expires_at']
    list_filter = ['is_active']
    search_fields = ['name', 'email', 'subscriber_code']
    readonly_fields = ['subscriber_code', 'created_at']
    actions = ['activate', 'deactivate']

    @admin.action(description='Activate selected subscriptions')
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Deactivate selected subscriptions')
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    readonly_fields = ['content', 'is_from_admin', 'created_at', 'is_read']
    extra = 0
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'visitor', 'subscriber', 'unread_by_admin', 'is_resolved', 'last_message_at']
    list_filter = ['is_resolved']
    search_fields = ['session_id']
    readonly_fields = ['session_id', 'created_at', 'last_message_at']
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'is_from_admin', 'content', 'created_at', 'is_read']
    list_filter = ['is_from_admin', 'is_read']


@admin.register(SessionLog)
class SessionLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'visitor', 'subscriber', 'timestamp']
    list_filter = ['action']
    readonly_fields = ['timestamp']
