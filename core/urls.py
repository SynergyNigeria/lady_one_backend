from django.urls import path
from . import views

urlpatterns = [
    # --- Public ---
    path('track/', views.track_visitor),
    path('subscribe/', views.subscribe),
    path('verify-code/', views.verify_code),
    path('chat/start/', views.start_conversation),
    path('chat/<str:session_id>/messages/', views.chat_messages),

    # --- Admin API ---
    path('admin-api/login/', views.admin_login),
    path('admin-api/stats/', views.admin_stats),
    path('admin-api/visitors/', views.admin_visitors),
    path('admin-api/subscribers/', views.admin_subscribers),
    path('admin-api/subscribers/create/', views.admin_create_subscriber),
    path('admin-api/subscribers/<int:pk>/', views.admin_subscriber_detail),
    path('admin-api/subscribers/<int:pk>/regenerate-code/', views.admin_regenerate_code),
    path('admin-api/conversations/', views.admin_conversations),
    path('admin-api/conversations/<int:pk>/messages/', views.admin_conversation_messages),
    path('admin-api/conversations/<int:pk>/reply/', views.admin_reply),
    path('admin-api/conversations/<int:pk>/resolve/', views.admin_resolve_conversation),
    path('admin-api/ban/', views.admin_ban),
    path('admin-api/logs/', views.admin_logs),
]
