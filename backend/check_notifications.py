#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from api.models import OverdueNotification

# Check sent notifications and recent notification history
sent_notifications = OverdueNotification.objects.filter(status='Sent').count()
pending_notifications = OverdueNotification.objects.exclude(status='Sent').count()

print(f"Sent notifications: {sent_notifications}")
print(f"Pending notifications: {pending_notifications}")
print(f"Total notifications: {sent_notifications + pending_notifications}")

print("\nRecent notifications:")
for notification in OverdueNotification.objects.order_by('-sent_at')[:2]:
    print(f"  {notification.notification_id}: {notification.notification_type} status={notification.status} sent_at={notification.sent_at}")
