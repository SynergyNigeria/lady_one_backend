from rest_framework import serializers
from .models import Visitor, Subscriber, Conversation, ChatMessage, SessionLog


class VisitorSerializer(serializers.ModelSerializer):
    has_subscriber = serializers.SerializerMethodField()

    class Meta:
        model = Visitor
        fields = ['id', 'ip_address', 'first_seen', 'last_seen', 'visit_count', 'is_banned', 'user_agent', 'has_subscriber']
        read_only_fields = ['id', 'first_seen', 'last_seen']

    def get_has_subscriber(self, obj):
        return hasattr(obj, 'subscriber')


class SubscriberSerializer(serializers.ModelSerializer):
    visitor_ip = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = ['id', 'name', 'email', 'phone', 'subscriber_code',
                  'created_at', 'expires_at', 'visitor_ip', 'is_expired', 'verified_by_admin']
        read_only_fields = ['id', 'subscriber_code', 'created_at']

    def get_visitor_ip(self, obj):
        return obj.visitor.ip_address if obj.visitor else None

    def get_is_expired(self, obj):
        return not obj.is_valid()


class ChatMessageSerializer(serializers.ModelSerializer):
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ['id', 'content', 'attachment_url', 'is_from_admin', 'created_at', 'is_read']
        read_only_fields = ['id', 'created_at']

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url


class ConversationSerializer(serializers.ModelSerializer):
    visitor_ip = serializers.SerializerMethodField()
    subscriber_code = serializers.SerializerMethodField()
    subscriber_name = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'session_id', 'visitor_ip', 'subscriber_code', 'subscriber_name',
                  'created_at', 'last_message_at', 'is_resolved',
                  'unread_by_admin', 'unread_by_user', 'last_message', 'message_count']

    def get_visitor_ip(self, obj):
        return obj.visitor.ip_address if obj.visitor else 'Unknown'

    def get_subscriber_code(self, obj):
        return obj.subscriber.subscriber_code if obj.subscriber else None

    def get_subscriber_name(self, obj):
        return obj.subscriber.name if obj.subscriber else None

    def get_last_message(self, obj):
        msg = obj.messages.last()
        return msg.content[:100] if msg else None

    def get_message_count(self, obj):
        return obj.messages.count()


class SessionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionLog
        fields = ['id', 'action', 'timestamp', 'metadata']
