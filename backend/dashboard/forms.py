from django import forms
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from api.models import Application


phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='Contact number must start with 09 and contain exactly 11 digits.',
)


class RegistrationForm(forms.Form):
    """Form for user registration only - creates Django User account"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Username',
            'required': 'required'
        }),
        help_text='Your login username'
    )

    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Full Name',
            'required': 'required'
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Email Address',
            'required': 'required'
        })
    )

    password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Password',
            'required': 'required'
        }),
        help_text='At least 8 characters'
    )
    
    password_confirm = forms.CharField(
        max_length=128,
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Confirm Password',
            'required': 'required'
        })
    )

    phone = forms.CharField(
        max_length=11,
        min_length=11,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': '09XXXXXXXXX',
            'inputmode': 'numeric',
            'pattern': '09[0-9]{9}',
            'maxlength': '11',
            'required': 'required'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        # Check username availability
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken. Please choose another.')
        
        # Check password match
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Passwords do not match.')
            if len(password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters long.')
        
        return cleaned_data


class ApplicationRegistrationForm(forms.ModelForm):
    LOCATION_CHOICES = [
        ('', '-- Select Location --'),
        ('Cambaog', 'Cambaog'),
        ('Talampas', 'Talampas'),
        ('San Pedro', 'San Pedro'),
        ('Malamig', 'Malamig'),
        ('Bunga Mayor', 'Bunga Mayor'),
        ('Bunga Menor', 'Bunga Menor'),
        ('Liciada', 'Liciada'),
    ]
    
    PLAN_CHOICES = [
        ('', '-- Select Plan --'),
        ('Basic 25Mbps', 'Basic 25Mbps - ₱499/month'),
        ('Standard 50Mbps', 'Standard 50Mbps - ₱799/month'),
        ('Premium 100Mbps', 'Premium 100Mbps - ₱1,299/month'),
    ]
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Username',
            'required': 'required'
        }),
        help_text='Your login username'
    )
    
    password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Password',
            'required': 'required'
        }),
        help_text='At least 8 characters'
    )
    
    password_confirm = forms.CharField(
        max_length=128,
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Confirm Password',
            'required': 'required'
        })
    )
    
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Full Name',
            'required': 'required'
        })
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Email Address',
            'required': 'required'
        })
    )
    
    phone = forms.CharField(
        max_length=11,
        min_length=11,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': '09XXXXXXXXX',
            'inputmode': 'numeric',
            'pattern': '09[0-9]{9}',
            'maxlength': '11',
            'required': 'required'
        })
    )
    
    location = forms.ChoiceField(
        choices=LOCATION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'required': 'required'
        })
    )
    
    house_no = forms.CharField(
        max_length=50,
        label='House No.',
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'House Number',
            'required': 'required'
        })
    )
    
    street_no = forms.CharField(
        max_length=100,
        label='Street/Barangay',
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Street or Barangay Name',
            'required': 'required'
        })
    )
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'required': 'required'
        })
    )
    
    class Meta:
        model = Application
        fields = ['name', 'email', 'phone', 'plan']
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        location = cleaned_data.get('location')
        house_no = cleaned_data.get('house_no')
        street_no = cleaned_data.get('street_no')
        
        # Check username availability
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken. Please choose another.')
        
        # Check password match
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Passwords do not match.')
            if len(password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters long.')
        
        if not location:
            raise forms.ValidationError('Please select a location.')
        
        # Combine address fields
        address = f"{house_no}, {street_no}, {location}"
        cleaned_data['address'] = address
        
        return cleaned_data


class ApplicationForm(forms.ModelForm):
    """Form for existing users to create new applications"""
    
    LOCATION_CHOICES = [
        ('', '-- Select Location --'),
        ('Cambaog', 'Cambaog'),
        ('Talampas', 'Talampas'),
        ('San Pedro', 'San Pedro'),
        ('Malamig', 'Malamig'),
        ('Bunga Mayor', 'Bunga Mayor'),
        ('Bunga Menor', 'Bunga Menor'),
        ('Liciada', 'Liciada'),
    ]
    
    PLAN_CHOICES = [
        ('', '-- Select Plan --'),
        ('Basic 25Mbps', 'Basic 25Mbps - ₱499/month'),
        ('Standard 50Mbps', 'Standard 50Mbps - ₱799/month'),
        ('Premium 100Mbps', 'Premium 100Mbps - ₱1,299/month'),
    ]
    
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Full Name',
            'required': 'required',
            'readonly': 'readonly'
        })
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Email Address',
            'required': 'required',
            'readonly': 'readonly'
        })
    )
    
    phone = forms.CharField(
        max_length=11,
        min_length=11,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': '09XXXXXXXXX',
            'inputmode': 'numeric',
            'pattern': '09[0-9]{9}',
            'maxlength': '11',
            'required': 'required',
            'readonly': 'readonly'
        })
    )
    
    location = forms.ChoiceField(
        choices=LOCATION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'required': 'required'
        })
    )
    
    house_no = forms.CharField(
        max_length=50,
        label='House No.',
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'House Number',
            'required': 'required'
        })
    )
    
    street_no = forms.CharField(
        max_length=100,
        label='Street/Barangay',
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'placeholder': 'Street or Barangay Name',
            'required': 'required'
        })
    )
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none',
            'required': 'required'
        })
    )

    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        widget=forms.HiddenInput()
    )

    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        widget=forms.HiddenInput()
    )
    
    class Meta:
        model = Application
        fields = ['name', 'email', 'phone', 'plan']
    
    def clean(self):
        cleaned_data = super().clean()
        location = cleaned_data.get('location')
        house_no = cleaned_data.get('house_no')
        street_no = cleaned_data.get('street_no')
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if not location:
            raise forms.ValidationError('Please select a location.')

        if latitude is None or longitude is None:
            raise forms.ValidationError('Please click "Use My Current Location" and allow location access before submitting.')

        # Combine address fields
        address = f"{house_no}, {street_no}, {location}"
        cleaned_data['address'] = address

        return cleaned_data


class NotificationSettingsForm(forms.Form):
    """Form for managing user notification preferences"""
    
    NOTIFICATION_METHOD_CHOICES = [
        ('email', 'Email Only'),
        ('sms', 'SMS Only'),
        ('both', 'Email & SMS'),
    ]
    
    notifications_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Enable Notifications',
        help_text='Disable this to stop all notifications'
    )
    
    notification_method = forms.ChoiceField(
        choices=NOTIFICATION_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Notification Method',
        help_text='Choose how you want to receive notifications'
    )
    
    grace_period_days = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'type': 'number',
        }),
        label='Grace Period (Days)',
        help_text='Number of days before automatic disconnection'
    )
    
    send_first_notice = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Send First Notice (Days 1-2)',
        help_text='Friendly reminder on days 1-2 of being overdue'
    )
    
    send_second_notice = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Send Second Notice (Day 3)',
        help_text='Urgent notice on day 3 (final day of grace)'
    )
    
    send_disconnection_warning = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Send Disconnection Warning (Day 4+)',
        help_text='Final warning when service is about to be disconnected'
    )
    
    auto_disconnect_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Auto-Disconnect After Grace Period',
        help_text='Service will be automatically disconnected after grace period'
    )
    
    allow_email_reminders = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Allow Email Reminders',
        help_text='Receive payment reminders via email'
    )
    
    allow_sms_reminders = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Allow SMS Reminders',
        help_text='Receive payment reminders via SMS'
    )


class NotificationTemplateForm(forms.Form):
    """Form for editing notification templates"""
    
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
    
    template_type = forms.ChoiceField(
        choices=TEMPLATE_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'style': 'background-color: #1e293b; color: #e2e8f0; border-color: #334155;',
            'disabled': True,
        }),
        label='Template Type'
    )
    
    channel = forms.ChoiceField(
        choices=CHANNEL_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'style': 'background-color: #1e293b; color: #e2e8f0; border-color: #334155;',
            'disabled': True,
        }),
        label='Channel'
    )
    
    subject = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'style': 'background-color: #1e293b; color: #e2e8f0; border-color: #334155;',
            'placeholder': 'Email subject (leave blank for SMS)'
        }),
        label='Email Subject',
        help_text='Only for Email templates'
    )
    
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'style': 'background-color: #1e293b; color: #e2e8f0; border-color: #334155; min-height: 520px; max-height: 72vh; resize: vertical;',
            'placeholder': 'Message body',
            'rows': 18
        }),
        label='Message Body',
        help_text='Available placeholders: {customer_name}, {amount_due}, {days_overdue}, {plan}, {client_id}, {due_date}, {days_remaining}'
    )
