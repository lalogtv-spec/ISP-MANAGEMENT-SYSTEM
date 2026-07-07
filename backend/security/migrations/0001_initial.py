# Generated migration for security models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SecuritySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('otp_expiry_minutes', models.IntegerField(default=15)),
                ('max_login_attempts', models.IntegerField(default=5)),
                ('lockout_duration_minutes', models.IntegerField(default=30)),
                ('session_timeout_minutes', models.IntegerField(default=30)),
                ('require_mfa', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name_plural': 'Security Settings',
            },
        ),
        migrations.CreateModel(
            name='UserSecurityProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('admin', 'Administrator'), ('operator', 'Operator'), ('client', 'Client'), ('viewer', 'Viewer')], default='client', max_length=20)),
                ('facial_data_enrolled', models.BooleanField(default=False)),
                ('fingerprint_enrolled', models.BooleanField(default=False)),
                ('mfa_enabled', models.BooleanField(default=False)),
                ('mfa_method', models.CharField(default='', max_length=100)),
                ('account_locked', models.BooleanField(default=False)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('failed_login_attempts', models.IntegerField(default=0)),
                ('password_changed_at', models.DateTimeField(auto_now_add=True)),
                ('password_expiry_days', models.IntegerField(default=90)),
                ('force_password_change', models.BooleanField(default=False)),
                ('last_login_ip', models.CharField(blank=True, max_length=45)),
                ('last_login_timestamp', models.DateTimeField(blank=True, null=True)),
                ('active_session_id', models.CharField(blank=True, max_length=255)),
                ('inactive_lockout_enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='security_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'User Security Profiles',
            },
        ),
        migrations.CreateModel(
            name='OTPLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('otp_code', models.CharField(max_length=6)),
                ('email_sent_to', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('active', 'Active'), ('used', 'Used'), ('expired', 'Expired'), ('invalid', 'Invalid')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('verification_attempts', models.IntegerField(default=0)),
                ('max_attempts', models.IntegerField(default=5)),
                ('ip_address', models.CharField(blank=True, max_length=45)),
                ('user_agent', models.TextField(blank=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='otp_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MFASettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=False)),
                ('method', models.CharField(choices=[('password_otp', 'Password + OTP'), ('password_facial', 'Password + Facial Recognition'), ('password_fingerprint', 'Password + Fingerprint'), ('password_otp_facial', 'Password + OTP + Facial'), ('password_otp_fingerprint', 'Password + OTP + Fingerprint')], default='password_otp', max_length=50)),
                ('backup_codes', models.TextField(blank=True)),
                ('backup_codes_used', models.TextField(blank=True)),
                ('require_on_every_login', models.BooleanField(default=False)),
                ('require_on_suspicious_login', models.BooleanField(default=True)),
                ('enabled_at', models.DateTimeField(blank=True, null=True)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mfa_settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'MFA Settings',
            },
        ),
        migrations.CreateModel(
            name='LoginAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150)),
                ('status', models.CharField(choices=[('success', 'Successful'), ('failed', 'Failed'), ('locked', 'Account Locked'), ('otp_required', 'OTP Required'), ('biometric_required', 'Biometric Required')], max_length=20)),
                ('ip_address', models.CharField(max_length=45)),
                ('user_agent', models.TextField()),
                ('device_info', models.CharField(blank=True, max_length=255)),
                ('attempted_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('reason', models.TextField(blank=True)),
                ('geolocation', models.CharField(blank=True, max_length=255)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='login_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-attempted_at'],
            },
        ),
        migrations.CreateModel(
            name='BiometricVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verification_type', models.CharField(choices=[('facial', 'Facial Recognition'), ('fingerprint', 'Fingerprint')], max_length=20)),
                ('result', models.CharField(choices=[('success', 'Successful'), ('failed', 'Failed'), ('quality_low', 'Quality Too Low'), ('not_matched', 'No Match')], max_length=20)),
                ('match_confidence', models.FloatField(default=0.0)),
                ('match_threshold', models.FloatField(default=0.95)),
                ('attempted_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.CharField(blank=True, max_length=45)),
                ('device_info', models.CharField(blank=True, max_length=255)),
                ('session_id', models.CharField(blank=True, max_length=255)),
                ('reason', models.CharField(blank=True, max_length=100)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='biometric_verifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-attempted_at'],
            },
        ),
        migrations.CreateModel(
            name='BiometricData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('biometric_type', models.CharField(choices=[('facial', 'Facial Recognition'), ('fingerprint', 'Fingerprint')], max_length=20)),
                ('template_data', models.TextField()),
                ('template_hash', models.CharField(max_length=255, unique=True)),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('enrolled_from_ip', models.CharField(blank=True, max_length=45)),
                ('enrollment_device', models.CharField(blank=True, max_length=255)),
                ('enrollment_quality_score', models.FloatField(default=0.0)),
                ('enrollment_confidence', models.FloatField(default=0.0)),
                ('is_active', models.BooleanField(default=True)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='biometric_data', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'biometric_type')},
            },
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('login', 'Login'), ('logout', 'Logout'), ('otp_request', 'OTP Requested'), ('otp_verify', 'OTP Verification'), ('facial_enroll', 'Facial Enrollment'), ('facial_verify', 'Facial Verification'), ('fingerprint_enroll', 'Fingerprint Enrollment'), ('fingerprint_verify', 'Fingerprint Verification'), ('mfa_enable', 'MFA Enabled'), ('mfa_disable', 'MFA Disabled'), ('password_change', 'Password Changed'), ('account_lockout', 'Account Locked'), ('account_unlock', 'Account Unlocked'), ('permission_change', 'Permission Changed'), ('role_change', 'Role Changed'), ('admin_action', 'Administrative Action'), ('security_event', 'Security Event')], max_length=50)),
                ('description', models.TextField()),
                ('ip_address', models.CharField(max_length=45)),
                ('user_agent', models.TextField(blank=True)),
                ('device_info', models.CharField(blank=True, max_length=255)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(default='success', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('session_id', models.CharField(blank=True, max_length=255)),
                ('related_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='related_audit_logs', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='SessionManagement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=255, unique=True)),
                ('ip_address', models.CharField(max_length=45)),
                ('user_agent', models.TextField()),
                ('device_info', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('force_logout', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        # Add database indexes
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', '-timestamp'], name='auditlog_user_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action_type', '-timestamp'], name='auditlog_action_timestamp_idx'),
        ),
    ]
