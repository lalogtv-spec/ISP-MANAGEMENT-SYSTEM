import json

from django.test import SimpleTestCase

from .forms import FaceEnrollmentForm


class FaceEnrollmentFormTests(SimpleTestCase):
    def test_accepts_json_array_payload(self):
        payload = json.dumps([
            'data:image/jpeg;base64,abc123',
            'data:image/jpeg;base64,def456',
        ])

        form = FaceEnrollmentForm(data={'face_image_data': payload})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['face_image_data'], [
            'data:image/jpeg;base64,abc123',
            'data:image/jpeg;base64,def456',
        ])

    def test_rejects_invalid_payload_entries(self):
        payload = json.dumps(['data:image/jpeg;base64,abc123', 'not-an-image'])

        form = FaceEnrollmentForm(data={'face_image_data': payload})

        self.assertFalse(form.is_valid())
        self.assertIn('face_image_data', form.errors)
