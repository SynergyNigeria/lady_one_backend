#!/usr/bin/env python
"""
One-time setup: creates a default admin user and prints the auth token.
Run: python setup_admin.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ladyswap.settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

USERNAME = 'admin'
PASSWORD = 'admin123'
EMAIL = 'admin@ladyswap.com'

if not User.objects.filter(username=USERNAME).exists():
    user = User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
    token = Token.objects.create(user=user)
    print(f'[OK] Admin created:  {USERNAME} / {PASSWORD}')
    print(f'[OK] Auth token:     {token.key}')
else:
    user = User.objects.get(username=USERNAME)
    token, created = Token.objects.get_or_create(user=user)
    print(f'[OK] Admin already exists: {USERNAME}')
    print(f'[OK] Auth token: {token.key}')

print('\nAdmin panel: http://localhost:5500/admin-panel.html')
print('Django admin: http://localhost:8000/django-admin/')
