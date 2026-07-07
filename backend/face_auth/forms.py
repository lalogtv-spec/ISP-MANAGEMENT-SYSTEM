import json

from django import forms


class EnableFaceLoginForm(forms.Form):
    enable_face_login = forms.BooleanField(
        required=False,
        label='Enable facial login',
        help_text='Allow face login after successful password authentication.'
    )


class FaceEnrollmentForm(forms.Form):
    face_image_data = forms.CharField(required=True)

    def clean_face_image_data(self):
        value = self.cleaned_data['face_image_data']
        if not value:
            raise forms.ValidationError('No face images captured.')

        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return value

        if isinstance(parsed, list):
            if not parsed or not all(isinstance(item, str) and item.startswith('data:image/') for item in parsed):
                raise forms.ValidationError('Invalid face capture data.')
            return parsed

        if isinstance(parsed, str):
            return parsed

        raise forms.ValidationError('Invalid face capture data.')


class FaceLoginForm(forms.Form):
    username = forms.CharField(required=True, max_length=150)
    face_image_data = forms.CharField(required=True)
