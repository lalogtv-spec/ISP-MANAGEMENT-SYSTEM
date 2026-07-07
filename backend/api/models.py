from django.db import models
from django.contrib.auth.models import User

class Client(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Overdue', 'Overdue'),
        ('Disconnected', 'Disconnected'),
    ]
    
    client_id = models.CharField(max_length=10, unique=True, primary_key=True)
    name = models.CharField(max_length=255)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    plan = models.CharField(max_length=100)
    fee = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    due_date = models.DateField()
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    joined = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class Application(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
    ]
    
    app_id = models.CharField(max_length=10, unique=True, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    address = models.TextField()
    plan = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.app_id} - {self.name}"


class ApplicationDecision(models.Model):
    STATUS_CHOICES = [
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
    ]

    app_id = models.CharField(max_length=10, unique=True, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    plan = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reason = models.TextField(blank=True, default='')
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.app_id} - {self.status}"


class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    ]
    
    ticket_id = models.CharField(max_length=20, unique=True, primary_key=True)
    client = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    description = models.TextField()
    attachment = models.ImageField(upload_to='ticket_attachments/', null=True, blank=True)
    assigned = models.CharField(max_length=255, default='Unassigned')
    created = models.DateField()
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    hide_from_notifications = models.BooleanField(default=False)
    notification_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return self.ticket_id


class Payment(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Rejected', 'Rejected'),
    ]
    
    payment_id = models.CharField(max_length=10, unique=True, primary_key=True)
    client = models.CharField(max_length=255)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=50)
    method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    hide_from_notifications = models.BooleanField(default=False)
    notification_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.payment_id} - {self.client} - {self.amount}"


class PaymentMethod(models.Model):
    """Persisted payment methods for clients (saved payment instruments)."""
    id = models.UUIDField(primary_key=True, default=__import__('uuid').uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    detail = models.CharField(max_length=255, blank=True)
    brand = models.CharField(max_length=50, blank=True)
    verified = models.BooleanField(default=False)
    default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.display_name} ({self.client.client_id})"


class OverdueNotification(models.Model):
    NOTIFICATION_TYPE = [
        ('First Notice', 'First Notice (Day 0-1)'),
        ('Second Notice', 'Second Notice (Day 2-3)'),
        ('Disconnection Warning', 'Disconnection Warning (Day 4+)'),
    ]
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Sent', 'Sent'),
        ('Failed', 'Failed'),
    ]
    
    notification_id = models.CharField(max_length=20, unique=True, primary_key=True)
    client = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    email_response = models.TextField(null=True, blank=True)
    sms_response = models.TextField(null=True, blank=True)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    days_overdue = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    hide_from_notifications = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_id} - {self.client} ({self.notification_type})"


class NotificationSettings(models.Model):
    NOTIFICATION_METHOD_CHOICES = [
        ('email', 'Email Only'),
        ('sms', 'SMS Only'),
        ('both', 'Email & SMS'),
    ]
    
    client_id = models.CharField(max_length=10, unique=True, primary_key=True)
    client_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Notification preferences
    notifications_enabled = models.BooleanField(default=True, help_text='Enable/disable all notifications')
    notification_method = models.CharField(max_length=10, choices=NOTIFICATION_METHOD_CHOICES, default='both')
    
    # Grace period settings (in days)
    grace_period_days = models.IntegerField(default=3, help_text='Days before disconnection after due date')
    
    # Notification triggers
    send_first_notice = models.BooleanField(default=True, help_text='Send notice on day 1-2 of being overdue')
    send_second_notice = models.BooleanField(default=True, help_text='Send urgent notice on day 3')
    send_disconnection_warning = models.BooleanField(default=True, help_text='Send final warning after day 3')
    
    # Auto-disconnect setting
    auto_disconnect_enabled = models.BooleanField(default=True, help_text='Automatically disconnect after grace period')
    
    # Contact preferences
    allow_email_reminders = models.BooleanField(default=True)
    allow_sms_reminders = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notification Settings'
        verbose_name_plural = 'Notification Settings'
    
    def __str__(self):
        return f"Settings for {self.client_name} ({self.client_id})"


# SMSNotificationLog and EmailNotificationLog removed per request.
# Use `OverdueNotification` and `NotificationTemplate` to track notifications and templates.


class NotificationTemplate(models.Model):
    """
    Store editable notification templates for SMS and Email
    """
    TEMPLATE_TYPES = [
        ('First Notice', 'First Notice'),
        ('Second Notice', 'Second Notice'),
        ('Disconnection Warning', 'Disconnection Warning'),
        ('Service Scheduled', 'Service Scheduled'),
        ('Service Rescheduled', 'Service Rescheduled'),
        ('Payment Receipt', 'Payment Receipt'),
    ]
    
    CHANNEL_TYPES = [
        ('Email', 'Email'),
        ('SMS', 'SMS'),
    ]
    
    template_id = models.CharField(max_length=50, unique=True, primary_key=True)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    channel = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    subject = models.CharField(max_length=255, blank=True, help_text="For Email only")
    body = models.TextField(help_text="Use {customer_name}, {amount_due}, {days_overdue}, {plan}, {client_id}, {due_date}, {days_remaining}, {ticket_id}, {date}, {time}, {issue}, {address} as placeholders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('template_type', 'channel')
        ordering = ['template_type', 'channel']
    
    def __str__(self):
        return f"{self.template_type} - {self.channel}"
    
    def save(self, *args, **kwargs):
        """Auto-generate template_id"""
        if not self.template_id:
            self.template_id = f"{self.template_type.replace(' ', '_')}_{self.channel}"
        super().save(*args, **kwargs)


class ActivityLog(models.Model):
    """
    Track all system activities: client changes, payments, application status changes
    """
    ACTIVITY_TYPES = [
        ('client_created', 'Client Created'),
        ('client_edited', 'Client Edited'),
        ('client_deleted', 'Client Deleted'),
        ('payment_recorded', 'Payment Recorded'),
        ('application_submitted', 'Application Submitted'),
        ('application_approved', 'Application Approved'),
        ('application_declined', 'Application Declined'),
        ('application_deleted', 'Application Deleted'),
        ('ticket_created', 'Ticket Created'),
        ('ticket_scheduled', 'Ticket Scheduled'),
        ('ticket_updated', 'Ticket Updated'),
        ('ticket_resolved', 'Ticket Resolved'),
        ('ticket_closed', 'Ticket Closed'),
    ]
    
    activity_id = models.AutoField(primary_key=True)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    entity_type = models.CharField(max_length=50)  # 'Client', 'Payment', 'Application'
    entity_id = models.CharField(max_length=50)  # client_id, payment_id, app_id
    entity_name = models.CharField(max_length=255)  # Client name, App ID, etc.
    description = models.TextField()  # Details about what happened
    old_value = models.TextField(blank=True, null=True)  # Previous value for edits
    new_value = models.TextField(blank=True, null=True)  # New value for edits
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # For payments
    performed_by = models.CharField(max_length=255, blank=True)  # Admin/User who performed action
    created_at = models.DateTimeField(auto_now_add=True)
    is_new = models.BooleanField(default=True)  # Track if admin has seen this activity
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_new']),
        ]
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.entity_name} ({self.created_at})"
