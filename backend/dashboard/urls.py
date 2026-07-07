from django.urls import path
from . import views
from . import client_views
from . import admin_views

app_name = 'dashboard'

urlpatterns = [
    # Registration URLs
    path('register/', views.register, name='register'),
    path('registration-success/', views.registration_success, name='registration-success'),
    path('application/<str:app_id>/', views.application_detail, name='application-detail'),
    path('application-status/<str:app_id>/', views.application_status, name='application-status'),
    path('new-application/', views.new_application, name='new_application'),
    
    # Admin URLs
    path('', views.dashboard, name='dashboard'),
    path('admin/colab/export/', views.export_colab_bundle_view, name='export-colab-bundle'),
    path('admin/cloudflare/start/', views.start_cloudflare_tunnel_view, name='start-cloudflare-tunnel'),
    path('auth/face-login/begin/', views.begin_fingerprint_login, name='face-login-begin'),
    path('auth/face-login/finish/', views.complete_fingerprint_login, name='face-login-finish'),
    path('auth/fingerprint-login/begin/', views.begin_fingerprint_login, name='fingerprint-login-begin'),
    path('auth/fingerprint-login/finish/', views.complete_fingerprint_login, name='fingerprint-login-finish'),
    path('clients/', views.clients_list, name='clients'),
    path('clients/list/', views.clients_list, name='clients_list'),
    path('clients/new/', views.client_create, name='client_create'),
    path('clients/<str:client_id>/', views.client_detail, name='client_detail'),
    path('clients/<str:client_id>/edit/', views.client_edit, name='client_edit'),
    path('clients/<str:client_id>/delete/', views.client_delete, name='client_delete'),
    path('applications/', views.applications_list, name='applications'),
    path('payments/', views.payments_list, name='payments'),
    path('payments/list/', views.payments_list, name='payments_list'),
    path('tickets/', views.tickets_list, name='tickets'),
    path('tickets/new/', views.ticket_create, name='ticket_create'),
    path('tickets/<str:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<str:ticket_id>/schedule/', views.ticket_schedule, name='ticket_schedule'),
    path('tickets/<str:ticket_id>/status/', views.ticket_update_status, name='ticket_update_status'),
    path('tickets/<str:ticket_id>/resolve/', views.ticket_resolve, name='ticket_resolve'),
    path('tickets/<str:ticket_id>/delete/', views.ticket_delete, name='ticket_delete'),
    path('logout/', views.logout_view, name='logout'),
    path('mfa/phone-fingerprint/begin/', views.begin_login_phone_fingerprint_assertion, name='login-phone-fingerprint-begin'),
    path('mfa/phone-fingerprint/finish/', views.complete_login_phone_fingerprint_assertion, name='login-phone-fingerprint-finish'),
    path('mfa/phone-fingerprint/reregister/begin/', views.begin_login_mobile_passkey_enrollment, name='login-mobile-passkey-reregister-begin'),
    path('mfa/phone-fingerprint/reregister/finish/', views.complete_login_mobile_passkey_enrollment, name='login-mobile-passkey-reregister-finish'),
    
    # Client URLs
    path('client/', client_views.client_dashboard, name='client-dashboard'),
    path('client/account/', client_views.client_account, name='client-account'),
    path('client/security-settings-v2/', client_views.security_settings, name='security-settings'),
    path('client/security-settings/', client_views.security_settings_legacy, name='security-settings-legacy'),
    path('client/api/mobile-biometric/enroll/options/', client_views.begin_mobile_passkey_enrollment, name='mobile-biometric-enroll-options'),
    path('client/api/mobile-biometric/enroll/finish/', client_views.complete_mobile_passkey_enrollment, name='mobile-biometric-enroll-finish'),
    path('client/api/mobile-biometric/assert/options/', client_views.begin_mobile_passkey_assertion, name='mobile-biometric-assert-options'),
    path('client/api/mobile-biometric/assert/finish/', client_views.complete_mobile_passkey_assertion, name='mobile-biometric-assert-finish'),
    path('client/biometric-prompt/dismiss/', client_views.dismiss_biometric_prompt, name='dismiss-biometric-prompt'),
    path('client/payments/', client_views.client_payments, name='client-payments'),
    path('client/process-payment/', client_views.process_payment, name='process-payment'),
    path('client/api/payment-methods/', client_views.client_payment_methods_api, name='client-payment-methods'),
    path('client/api/payment-methods/<uuid:method_id>/', client_views.client_payment_method_detail, name='client-payment-method-detail'),
    path('client/tickets/', client_views.client_tickets, name='client-tickets'),
    
    # GCash Payment URLs
    path('client/gcash-payment/', client_views.gcash_payment, name='gcash-payment'),
    path('client/stripe-payment/', client_views.stripe_payment, name='stripe-payment'),
    path('client/stripe-success/', client_views.stripe_success, name='stripe-success'),
    path('client/gcash-callback/', client_views.gcash_callback, name='gcash-callback'),
    path('api/gcash-webhook/', client_views.gcash_webhook, name='gcash-webhook'),
    path('api/stripe-webhook/', client_views.stripe_webhook, name='stripe-webhook'),
    path('test-gcash-payment/', client_views.test_gcash_payment, name='test-gcash-payment'),
    path('client/tickets/new/', client_views.client_ticket_create, name='client-ticket-create'),
    path('client/tickets/<str:ticket_id>/reschedule/', client_views.client_ticket_reschedule, name='client-ticket-reschedule'),
    path('admin/tickets/<str:ticket_id>/approve-reschedule/', views.approve_reschedule, name='approve-reschedule'),
    
    # Overdue Notification URLs
    path('test-overdue-notification/', client_views.test_overdue_notification, name='test-overdue-notification'),
    
    # Notification Settings
    path('client/notification-settings/', client_views.notification_settings, name='notification-settings'),
    path('client/notifications/', client_views.client_notifications, name='client-notifications'),
    path('client/mark-notification-read/', client_views.client_mark_notification_read, name='client-mark-notification-read'),
    path('client/delete-notification/', client_views.client_delete_notification, name='client-delete-notification'),
    
    # Admin Notification Dashboard
    path('admin/notification-dashboard/', admin_views.notification_dashboard, name='notification-dashboard'),
    path('admin/sms-log/', admin_views.sms_notification_log, name='sms-log'),
    path('admin/email-log/', admin_views.email_notification_log, name='email-log'),
    path('admin/notification-templates/', admin_views.manage_notification_templates, name='notification-templates'),
    path('admin/notification-templates/<str:template_id>/edit/', admin_views.edit_notification_template, name='edit-notification-template'),
    path('admin/audit-log/', admin_views.audit_log, name='audit-log'),
    path('admin/testing/', views.testing_panel, name='testing-panel'),
    path('admin/mark-notification-read/', admin_views.mark_notification_read, name='mark-notification-read'),
    path('admin/delete-notification/', admin_views.delete_notification, name='delete-notification'),
]

