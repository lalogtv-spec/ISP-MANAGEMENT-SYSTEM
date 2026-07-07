from django.contrib import admin
from .models import Client, Application, Ticket, Payment
from .activity_logger import (
    log_client_created, log_client_edited, log_client_deleted,
    log_payment_recorded, log_application_approved, log_application_declined,
    log_application_deleted
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'name', 'status', 'fee', 'due_date')
    list_filter = ('status', 'joined')
    search_fields = ('name', 'email', 'phone')
    ordering = ('-created_at',)
    
    def save_model(self, request, obj, form, change):
        """Log client creation and edits"""
        if change:
            # Client is being edited
            old_obj = Client.objects.get(pk=obj.pk)
            changes = {}
            
            # Check for changes
            if old_obj.name != obj.name:
                changes['name'] = {'old': old_obj.name, 'new': obj.name}
            if old_obj.plan != obj.plan:
                changes['plan'] = {'old': old_obj.plan, 'new': obj.plan}
            if old_obj.status != obj.status:
                changes['status'] = {'old': old_obj.status, 'new': obj.status}
            if old_obj.fee != obj.fee:
                changes['fee'] = {'old': str(old_obj.fee), 'new': str(obj.fee)}
            
            if changes:
                log_client_edited(obj.client_id, obj.name, changes, request.user.username)
        else:
            # New client
            log_client_created(obj.client_id, obj.name, request.user.username)
        
        super().save_model(request, obj, form, change)
    
    def delete_model(self, request, obj):
        """Log client deletion"""
        log_client_deleted(obj.client_id, obj.name, request.user.username)
        super().delete_model(request, obj)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('app_id', 'name', 'status', 'plan', 'latitude', 'longitude', 'date')
    list_filter = ('status', 'date')
    search_fields = ('name', 'email')
    ordering = ('-date',)
    
    def save_model(self, request, obj, form, change):
        """Log application status changes"""
        if change:
            # Application is being edited
            old_obj = Application.objects.get(pk=obj.pk)
            
            if old_obj.status != obj.status:
                if obj.status == 'Approved':
                    log_application_approved(obj.app_id, obj.name, obj.plan, request.user.username)
                elif obj.status == 'Declined':
                    log_application_declined(obj.app_id, obj.name, obj.plan, '', request.user.username)
        
        super().save_model(request, obj, form, change)
    
    def delete_model(self, request, obj):
        """Log application deletion"""
        log_application_deleted(obj.app_id, obj.name, obj.plan, request.user.username)
        super().delete_model(request, obj)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'client', 'priority', 'status', 'created')
    list_filter = ('status', 'priority', 'created')
    search_fields = ('ticket_id', 'client', 'category')
    ordering = ('-created',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'client', 'amount', 'status', 'date')
    list_filter = ('status', 'date')
    search_fields = ('payment_id', 'client')
    ordering = ('-date',)
    
    def save_model(self, request, obj, form, change):
        """Log payment recording"""
        if not change:
            # New payment
            log_payment_recorded(obj.payment_id, obj.client, obj.amount, obj.method, request.user.username)
        
        super().save_model(request, obj, form, change)
