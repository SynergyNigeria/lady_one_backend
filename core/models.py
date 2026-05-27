import secrets
import string
from django.db import models
from django.utils import timezone


def generate_subscriber_code():
    """Generate a unique 12-character subscription code like LS-XXXXXXXXXXXX."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = 'LS-' + ''.join(secrets.choice(alphabet) for _ in range(9))
        if not Subscriber.objects.filter(subscriber_code=code).exists():
            return code


class Visitor(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    visit_count = models.IntegerField(default=1)
    is_banned = models.BooleanField(default=False)
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f'Visitor {self.ip_address}'


class Subscriber(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True, default='')
    subscriber_code = models.CharField(max_length=20, unique=True, default=generate_subscriber_code)
    is_active = models.BooleanField(default=True)
    verified_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    visitor = models.OneToOneField(
        Visitor, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriber'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.subscriber_code})'

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class Conversation(models.Model):
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, null=True, blank=True, related_name='conversations')
    subscriber = models.ForeignKey(Subscriber, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    unread_by_admin = models.IntegerField(default=0)
    unread_by_user = models.IntegerField(default=0)

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        return f'Conversation {self.session_id[:12]}...'


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(blank=True, default='')
    attachment = models.FileField(upload_to='chat_uploads/', null=True, blank=True)
    is_from_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        sender = 'Admin' if self.is_from_admin else 'User'
        return f'{sender}: {self.content[:60]}'


class SessionLog(models.Model):
    ACTION_CHOICES = [
        ('visit', 'Page Visit'),
        ('subscribe', 'New Subscription'),
        ('verify', 'Code Verified'),
        ('chat', 'Chat Message'),
        ('ban', 'User Banned'),
        ('unban', 'User Unbanned'),
        ('deactivate', 'Subscription Deactivated'),
    ]

    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, null=True, blank=True, related_name='logs')
    subscriber = models.ForeignKey(Subscriber, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.action} at {self.timestamp:%Y-%m-%d %H:%M}'
