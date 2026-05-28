
from rest_framework.decorators import api_view, permission_classes, throttle_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import AnonRateThrottle
import html
import time
from django.utils import timezone
from django.contrib.auth import authenticate


def require_staff(fn):
    """Decorator to enforce is_staff on authenticated views."""
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)
        if not request.user.is_staff:
            return Response({'error': 'Staff access required.'}, status=403)
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

# Admin: Create new subscriber (auto code)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
@require_staff
def admin_create_subscriber(request):
    name = sanitize(request.data.get('name', ''))
    email = sanitize(request.data.get('email', '')).lower()
    phone = sanitize(request.data.get('phone', ''))
    if not name or not email:
        return Response({'error': 'Name and email are required.'}, status=400)
    if '@' not in email or '.' not in email:
        return Response({'error': 'Please enter a valid email address.'}, status=400)
    if Subscriber.objects.filter(email=email).exists():
        return Response({'error': 'Subscriber with this email already exists.'}, status=400)
    subscriber = Subscriber.objects.create(name=name, email=email, phone=phone)
    return Response({
        'success': True,
        'subscriber_code': subscriber.subscriber_code,
        'subscriber': SubscriberSerializer(subscriber).data,
        'message': f'Subscriber created. Code: {subscriber.subscriber_code}'
    }, status=201)

from .models import Visitor, Subscriber, Conversation, ChatMessage, SessionLog, generate_subscriber_code
from .serializers import (
    VisitorSerializer, SubscriberSerializer,
    ConversationSerializer, ChatMessageSerializer, SessionLogSerializer,
)

SUBSCRIBE_TRIGGER = 'i am ready to subscribe'
SUBSCRIBE_AUTO_REPLY = (
    'Accepted payment methods: Paypal, Cashapp, Apple Pay, Venmo, Chime, '
    'Bank transfer, Bitcoin and Apple gift card. Please select your preferred '
    'payment method.'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def sanitize(text):
    """Strip HTML and limit length to prevent injection."""
    return html.escape(str(text).strip())[:2000]


def require_staff(fn):
    """Decorator to enforce is_staff on authenticated views."""
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)
        if not request.user.is_staff:
            return Response({'error': 'Staff access required.'}, status=403)
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


class ChatThrottle(AnonRateThrottle):
    rate = '30/minute'


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def track_visitor(request):
    ip = get_client_ip(request)
    user_agent = sanitize(request.META.get('HTTP_USER_AGENT', ''))[:500]

    visitor, created = Visitor.objects.get_or_create(
        ip_address=ip,
        defaults={'user_agent': user_agent},
    )

    if not created:
        visitor.visit_count += 1
        visitor.user_agent = user_agent
        visitor.save(update_fields=['visit_count', 'user_agent', 'last_seen'])

    if visitor.is_banned:
        return Response({'banned': True, 'message': 'Access denied.'}, status=403)

    SessionLog.objects.create(
        visitor=visitor,
        action='visit',
        metadata={'page': sanitize(request.data.get('page', '/'))[:100]},
    )

    is_subscriber = hasattr(visitor, 'subscriber') and visitor.subscriber.is_valid()
    return Response({
        'visitor_id': visitor.id,
        'is_banned': visitor.is_banned,
        'visit_count': visitor.visit_count,
        'is_subscriber': is_subscriber,
        'created': created,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def subscribe(request):
    name = sanitize(request.data.get('name', ''))
    email = sanitize(request.data.get('email', '')).lower()
    phone = sanitize(request.data.get('phone', ''))

    if not name or not email:
        return Response({'error': 'Name and email are required.'}, status=400)

    if '@' not in email or '.' not in email:
        return Response({'error': 'Please enter a valid email address.'}, status=400)

    existing = Subscriber.objects.filter(email=email).first()
    if existing:
        if existing.is_valid():
            return Response({
                'already_subscribed': True,
                'subscriber_code': existing.subscriber_code,
                'name': existing.name,
                'message': f'You are already subscribed, {existing.name}!',
            })
        # Re-activate if deactivated
        existing.is_active = True
        existing.save(update_fields=['is_active'])
        return Response({
            'success': True,
            'subscriber_code': existing.subscriber_code,
            'name': existing.name,
            'message': f'Welcome back, {existing.name}! Your subscription has been reactivated.',
        })

    ip = get_client_ip(request)
    visitor = Visitor.objects.filter(ip_address=ip).first()

    subscriber = Subscriber.objects.create(
        name=name,
        email=email,
        phone=phone,
        visitor=visitor,
    )

    SessionLog.objects.create(
        visitor=visitor,
        subscriber=subscriber,
        action='subscribe',
        metadata={'email': email, 'ip': ip},
    )

    return Response({
        'success': True,
        'subscriber_code': subscriber.subscriber_code,
        'name': subscriber.name,
        'message': f'Welcome, {subscriber.name}! Save your subscription code — you will need it to log in.',
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def check_code(request):
    code = sanitize(request.data.get('code', '')).upper()

    if not code:
        return Response({'error': 'Subscription code is required.'}, status=400)

    subscriber = Subscriber.objects.filter(subscriber_code=code).first()
    if not subscriber:
        return Response({'exists': False, 'message': 'Invalid subscription code.'}, status=404)

    if not subscriber.is_active or (subscriber.expires_at and subscriber.expires_at < timezone.now()):
        return Response({'exists': False, 'message': 'Your subscription has expired or been deactivated.'}, status=403)

    return Response({
        'exists': True,
        'subscriber_code': subscriber.subscriber_code,
        'name': subscriber.name,
        'verified_by_admin': getattr(subscriber, 'verified_by_admin', False),
        'message': 'Booking code found.'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_code(request):
    code = sanitize(request.data.get('code', '')).upper()

    if not code:
        return Response({'error': 'Subscription code is required.'}, status=400)

    subscriber = Subscriber.objects.filter(subscriber_code=code).first()
    if not subscriber:
        return Response({'valid': False, 'message': 'Invalid subscription code.'}, status=404)


    # Only allow if verified_by_admin is True
    if not getattr(subscriber, 'verified_by_admin', False):
        return Response({
            'valid': False,
            'code_exists': True,
            'subscriber_code': subscriber.subscriber_code,
            'name': subscriber.name,
            'verified_by_admin': False,
            'message': 'Your booking code is not yet verified by admin.'
        }, status=403)

    if not subscriber.is_valid():
        return Response({'valid': False, 'message': 'Your subscription has expired or been deactivated.'}, status=403)

    ip = get_client_ip(request)
    visitor = Visitor.objects.filter(ip_address=ip).first()

    SessionLog.objects.create(
        visitor=visitor,
        subscriber=subscriber,
        action='verify',
        metadata={'ip': ip},
    )

    return Response({
        'valid': True,
        'subscriber_code': subscriber.subscriber_code,
        'name': subscriber.name,
        'email': subscriber.email,
        'expires_at': subscriber.expires_at,
        'verified_by_admin': getattr(subscriber, 'verified_by_admin', False),
        'message': f'Welcome back, {subscriber.name}!'
    })


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def start_conversation(request):
    session_id = sanitize(request.data.get('session_id', ''))[:100]
    if not session_id:
        return Response({'error': 'session_id is required.'}, status=400)

    ip = get_client_ip(request)
    visitor = Visitor.objects.filter(ip_address=ip).first()

    if visitor and visitor.is_banned:
        return Response({'error': 'Access denied.'}, status=403)

    subscriber_code = sanitize(request.data.get('subscriber_code', '')).upper()
    subscriber = Subscriber.objects.filter(subscriber_code=subscriber_code).first() if subscriber_code else None

    conversation, created = Conversation.objects.get_or_create(
        session_id=session_id,
        defaults={'visitor': visitor, 'subscriber': subscriber},
    )

    # Update subscriber link if now known
    if subscriber and not conversation.subscriber:
        conversation.subscriber = subscriber
        conversation.save(update_fields=['subscriber'])

    return Response({
        'conversation_id': conversation.id,
        'session_id': conversation.session_id,
        'unread_by_user': conversation.unread_by_user,
        'created': created,
    })


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([ChatThrottle])
def chat_messages(request, session_id):
    conversation = Conversation.objects.filter(session_id=session_id).first()
    if not conversation:
        return Response({'error': 'Conversation not found.'}, status=404)

    ip = get_client_ip(request)
    visitor = Visitor.objects.filter(ip_address=ip).first()
    if visitor and visitor.is_banned:
        return Response({'error': 'Access denied.'}, status=403)

    if request.method == 'GET':
        last_id = int(request.query_params.get('last_id', 0))
        messages = conversation.messages.filter(id__gt=last_id)

        # Mark admin replies as read by user
        unread_admin = messages.filter(is_from_admin=True, is_read=False)
        if unread_admin.exists():
            unread_admin.update(is_read=True)
            conversation.unread_by_user = 0
            conversation.save(update_fields=['unread_by_user'])

        return Response({
            'messages': ChatMessageSerializer(messages, many=True, context={'request': request}).data,
            'conversation_id': conversation.id,
        })

    # POST — send a new message
    content = sanitize(request.data.get('content', ''))
    attachment = request.FILES.get('attachment')
    if not content and not attachment:
        return Response({'error': 'Message content or photo is required.'}, status=400)

    if len(content) > 1000:
        return Response({'error': 'Message too long (max 1000 characters).'}, status=400)

    if attachment:
        if not (attachment.content_type or '').startswith('image/'):
            return Response({'error': 'Only image uploads are allowed.'}, status=400)
        if attachment.size > 5 * 1024 * 1024:
            return Response({'error': 'Image is too large (max 5MB).'}, status=400)

    message = ChatMessage.objects.create(
        conversation=conversation,
        content=content,
        attachment=attachment,
        is_from_admin=False,
    )

    conversation.unread_by_admin += 1
    conversation.last_message_at = timezone.now()
    update_fields = ['unread_by_admin', 'last_message_at']

    if html.unescape(content).strip().lower() == SUBSCRIBE_TRIGGER:
        time.sleep(3)
        ChatMessage.objects.create(
            conversation=conversation,
            content=SUBSCRIBE_AUTO_REPLY,
            is_from_admin=True,
        )
        conversation.unread_by_user += 1
        conversation.last_message_at = timezone.now()
        update_fields.append('unread_by_user')

    conversation.save(update_fields=update_fields)

    SessionLog.objects.create(
        visitor=visitor,
        action='chat',
        metadata={'message_id': message.id, 'conversation': conversation.id},
    )

    return Response(ChatMessageSerializer(message, context={'request': request}).data, status=201)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    username = sanitize(request.data.get('username', ''))
    password = request.data.get('password', '')  # do not sanitize passwords

    if not username or not password:
        return Response({'error': 'Username and password are required.'}, status=400)

    user = authenticate(username=username, password=password)
    if not user or not user.is_staff:
        return Response({'error': 'Invalid credentials or insufficient permissions.'}, status=401)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'username': user.username})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_stats(request):
    return Response({
        'total_visitors': Visitor.objects.count(),
        'banned_visitors': Visitor.objects.filter(is_banned=True).count(),
        'total_subscribers': Subscriber.objects.count(),
        'active_subscribers': Subscriber.objects.filter(is_active=True).count(),
        'total_conversations': Conversation.objects.count(),
        'unread_conversations': Conversation.objects.filter(unread_by_admin__gt=0, is_resolved=False).count(),
        'open_conversations': Conversation.objects.filter(is_resolved=False).count(),
        'total_messages': ChatMessage.objects.count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_visitors(request):
    visitors = Visitor.objects.all()
    return Response(VisitorSerializer(visitors, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_subscribers(request):
    subscribers = Subscriber.objects.all()
    return Response(SubscriberSerializer(subscribers, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_subscriber_detail(request, pk): 
    subscriber = Subscriber.objects.filter(pk=pk).first()
    if not subscriber:
        return Response({'error': 'Subscriber not found.'}, status=404)

    allowed_fields = {'expires_at', 'name', 'phone', 'verified_by_admin'}
    data = {k: v for k, v in request.data.items() if k in allowed_fields}

    serializer = SubscriberSerializer(subscriber, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        action = 'deactivate' if data.get('verified_by_admin') is False else 'verify'
        SessionLog.objects.create(
            subscriber=subscriber,
            action=action,
            metadata={'changed_by': request.user.username, 'fields': list(data.keys())},
        )
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_regenerate_code(request, pk):
    subscriber = Subscriber.objects.filter(pk=pk).first()
    if not subscriber:
        return Response({'error': 'Subscriber not found.'}, status=404)

    old_code = subscriber.subscriber_code
    subscriber.subscriber_code = generate_subscriber_code()
    subscriber.save(update_fields=['subscriber_code'])

    SessionLog.objects.create(
        subscriber=subscriber,
        action='verify',
        metadata={'action': 'regenerate_code', 'old_code': old_code, 'by': request.user.username},
    )

    return Response({'subscriber_code': subscriber.subscriber_code})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_conversations(request):
    conversations = Conversation.objects.all()
    return Response(ConversationSerializer(conversations, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_conversation_messages(request, pk):
    conversation = Conversation.objects.filter(pk=pk).first()
    if not conversation:
        return Response({'error': 'Conversation not found.'}, status=404)

    # Mark user messages as read
    conversation.messages.filter(is_from_admin=False, is_read=False).update(is_read=True)
    if conversation.unread_by_admin > 0:
        conversation.unread_by_admin = 0
        conversation.save(update_fields=['unread_by_admin'])

    return Response({
        'conversation': ConversationSerializer(conversation).data,
        'messages': ChatMessageSerializer(conversation.messages.all(), many=True, context={'request': request}).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_reply(request, pk):
    conversation = Conversation.objects.filter(pk=pk).first()
    if not conversation:
        return Response({'error': 'Conversation not found.'}, status=404)

    content = sanitize(request.data.get('content', ''))
    if not content:
        return Response({'error': 'Message content is required.'}, status=400)

    message = ChatMessage.objects.create(
        conversation=conversation,
        content=content,
        is_from_admin=True,
    )

    conversation.unread_by_user += 1
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=['unread_by_user', 'last_message_at'])

    return Response(ChatMessageSerializer(message, context={'request': request}).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_resolve_conversation(request, pk):
    conversation = Conversation.objects.filter(pk=pk).first()
    if not conversation:
        return Response({'error': 'Conversation not found.'}, status=404)

    conversation.is_resolved = not conversation.is_resolved
    conversation.save(update_fields=['is_resolved'])
    return Response({'is_resolved': conversation.is_resolved})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_ban(request):
    visitor_id = request.data.get('visitor_id')
    ban = request.data.get('ban', True)

    visitor = Visitor.objects.filter(pk=visitor_id).first()
    if not visitor:
        return Response({'error': 'Visitor not found.'}, status=404)

    visitor.is_banned = bool(ban)
    visitor.save(update_fields=['is_banned'])

    action = 'ban' if ban else 'unban'
    SessionLog.objects.create(
        visitor=visitor,
        action=action,
        metadata={'by': request.user.username},
    )

    return Response({'is_banned': visitor.is_banned, 'ip': visitor.ip_address})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_staff
def admin_logs(request):
    logs = SessionLog.objects.select_related('visitor', 'subscriber').all()[:200]
    return Response(SessionLogSerializer(logs, many=True).data)
