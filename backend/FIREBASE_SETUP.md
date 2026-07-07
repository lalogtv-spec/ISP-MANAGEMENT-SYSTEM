# Firebase Backend Setup Guide

## ✅ Configuration Complete!

Your Firebase configuration has been updated with the project credentials:
- **Project ID**: ispmanagement-43a4c
- **Auth Domain**: ispmanagement-43a4c.firebaseapp.com
- **Storage Bucket**: ispmanagement-43a4c.firebasestorage.app

## 📋 Next Steps: Get Service Account Key

To complete the Firebase Admin SDK setup, you need to create a service account key:

### Step 1: Go to Firebase Console
1. Visit: https://console.firebase.google.com/
2. Select your project: **ispmanagement-43a4c**

### Step 2: Create Service Account Key
1. Click the **Settings ⚙️** icon (top-left)
2. Select **Project Settings**
3. Go to the **Service Accounts** tab
4. Click **Generate New Private Key**
5. A JSON file will be downloaded automatically

### Step 3: Save the File
Place the downloaded JSON file in the backend folder:
```
c:\Users\lalog\Videos\Internet Payment Tracking\backend\serviceAccountKey.json
```

### Step 4: Test Connection
Run this command to verify Firebase is connected:
```bash
cd backend
python manage.py shell
```

Then in the Python shell:
```python
from firebase_service import firebase
print(firebase.is_connected())  # Should print True
```

## 🔥 Firebase Features Available

After adding the service account key, you can use:

### Authentication
```python
from firebase_service import firebase

# Create a user
user = firebase.create_user(
    email='user@example.com',
    password='password123',
    display_name='John Doe'
)

# Verify token
decoded_token = firebase.verify_id_token(token)
```

### Firestore Database
```python
# Save data
firebase.save_to_firestore(
    collection='clients',
    doc_id='client_001',
    data={
        'name': 'John Doe',
        'email': 'john@example.com',
        'status': 'Active'
    }
)

# Get data
client_data = firebase.get_from_firestore('clients', 'client_001')
print(client_data)
```

## 📱 Web App Configuration

The web app configuration is ready in your settings:
```javascript
const firebaseConfig = {
    apiKey: "AIzaSyBnSAwEQK9kRbcLhUWJGlvPw3YjL0_1udc",
    authDomain: "ispmanagement-43a4c.firebaseapp.com",
    projectId: "ispmanagement-43a4c",
    storageBucket: "ispmanagement-43a4c.firebasestorage.app",
    messagingSenderId: "702529139565",
    appId: "1:702529139565:web:19bc7a6843cc84141a2064",
    measurementId: "G-M53SSGP35B"
};
```

## 🔐 Security Rules

Remember to set up your Firestore security rules in Firebase Console:

**Development Rules** (during testing):
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if true;
    }
  }
}
```

**Production Rules** (recommended):
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /clients/{clientId} {
      allow read, write: if request.auth.uid != null;
    }
    match /payments/{paymentId} {
      allow read, write: if request.auth.uid != null;
    }
  }
}
```

## 🆘 Troubleshooting

### Certificate file not found
- Make sure `serviceAccountKey.json` is in the backend folder
- Check the exact filename matches

### Import errors
- Install: `pip install firebase-admin`
- Update: `pip install --upgrade firebase-admin`

### Permission denied
- Update your Firestore security rules in Console
- Check service account has proper permissions

## ✨ Ready to Use!

Once you add the service account key, your Django app will automatically connect to Firebase on startup. Check the console logs for the ✅ confirmation message.
