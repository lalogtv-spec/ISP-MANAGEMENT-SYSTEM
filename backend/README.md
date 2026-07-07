# ISP Management System - Django Backend

A Django REST API backend for the ISP Management System with Firebase integration.

## Features

- **Client Management**: Track clients, subscriptions, and billing status
- **Application Processing**: Manage new ISP service applications
- **Support Tickets**: Handle customer support requests with priority levels
- **Payment Tracking**: Monitor and verify customer payments
- **Firebase Integration**: Authentication and optional Firestore database
- **REST API**: Full RESTful API with filtering and search capabilities

## Installation

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Firebase credentials:
```
FIREBASE_API_KEY=your-key
FIREBASE_AUTH_DOMAIN=your-domain
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-bucket
FIREBASE_MESSAGING_SENDER_ID=your-sender-id
FIREBASE_APP_ID=your-app-id
```

### 4. Setup Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Load Initial Data

```bash
python manage.py loaddata initial_data.json
```

## Running the Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`

## Stable Public Link

The temporary `trycloudflare.com` link changes whenever the tunnel restarts. If you want one fixed URL, use a named Cloudflare Tunnel and set these environment variables:

```env
PUBLIC_HOSTNAME=app.yourdomain.com
CLOUDFLARED_TUNNEL_NAME=netconnect-dev
ALLOWED_HOSTS=localhost,127.0.0.1,app.yourdomain.com
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,https://app.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://app.yourdomain.com
```

Then:

1. Log in to Cloudflare on this machine with `cloudflared tunnel login`
2. Create the tunnel once with `cloudflared tunnel create netconnect-dev`
3. Route your DNS hostname to it with `cloudflared tunnel route dns netconnect-dev app.yourdomain.com`
4. Start the app locally on `127.0.0.1:8000`
5. Run [`run_tunnel.ps1`](./run_tunnel.ps1)

If you leave those values blank, the project still works, but the public tunnel URL will stay temporary.

Quick copy/paste setup:

```bash
cloudflared tunnel login
cloudflared tunnel create netconnect-dev
cloudflared tunnel route dns netconnect-dev app.yourdomain.com
```

Then set:

```env
PUBLIC_HOSTNAME=app.yourdomain.com
CLOUDFLARED_TUNNEL_NAME=netconnect-dev
```

If you are on Windows, you can set the variables with:

```powershell
setx PUBLIC_HOSTNAME app.yourdomain.com
setx CLOUDFLARED_TUNNEL_NAME netconnect-dev
```

## API Endpoints

### Clients
- `GET /api/clients/` - List all clients
- `GET /api/clients/{id}/` - Get client details
- `POST /api/clients/` - Create new client
- `PUT /api/clients/{id}/` - Update client
- `DELETE /api/clients/{id}/` - Delete client
- `GET /api/clients/active/` - Get active clients
- `GET /api/clients/overdue/` - Get overdue clients

### Applications
- `GET /api/applications/` - List all applications
- `GET /api/applications/{id}/` - Get application details
- `POST /api/applications/` - Create new application
- `GET /api/applications/pending/` - Get pending applications

### Tickets
- `GET /api/tickets/` - List all tickets
- `GET /api/tickets/{id}/` - Get ticket details
- `POST /api/tickets/` - Create new ticket
- `PUT /api/tickets/{id}/` - Update ticket
- `GET /api/tickets/open_tickets/` - Get open tickets
- `GET /api/tickets/critical/` - Get critical tickets

### Payments
- `GET /api/payments/` - List all payments
- `GET /api/payments/{id}/` - Get payment details
- `POST /api/payments/` - Create new payment
- `GET /api/payments/pending/` - Get pending payments
- `GET /api/payments/verified/` - Get verified payments

## Firebase Setup

### Get Service Account Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Settings → Service Accounts
4. Click "Generate New Private Key"
5. Save as `serviceAccountKey.json` in the `backend/` folder

## Frontend Integration

Update your React frontend API calls:

```javascript
// Before
const data = CLIENTS;

// After
const response = await fetch('http://localhost:8000/api/clients/');
const data = await response.json();
```

## Admin Panel

Access Django admin at `http://localhost:8000/admin/`
Login with your superuser credentials.

## Database

- SQLite (default) for local development
- Can be switched to PostgreSQL for production

## CORS Configuration

The backend is configured to accept requests from:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000` (React dev server)
- `http://127.0.0.1:5173`

Modify `CORS_ALLOWED_ORIGINS` in `.env` to change this.

## Security

- Change `SECRET_KEY` in `.env` for production
- Use environment variables for sensitive data
- Enable HTTPS in production
- Update `ALLOWED_HOSTS` with your domain

## Development Notes

- Uses Django ORM with SQLite
- Optional Firestore integration via Firebase Admin SDK
- RESTful API with Django REST Framework
- Pagination: 10 items per page (configurable)
- Filtering by status, search by name/email/phone

## Troubleshooting

**Import Error: No module named 'firebase_admin'**
```bash
pip install firebase-admin
```

**CORS Error**
- Make sure frontend URL is in `CORS_ALLOWED_ORIGINS`
- Restart Django server after changing `.env`

**Firebase Not Initializing**
- Ensure `serviceAccountKey.json` exists in backend folder
- Check Firebase credentials in `.env`

