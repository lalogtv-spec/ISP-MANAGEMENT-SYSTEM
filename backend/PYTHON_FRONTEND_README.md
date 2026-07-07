# ISP Management System - Python/Django Frontend

A complete ISP Management System built with **Python/Django** frontend and backend with **Firebase** integration.

## 🎯 Stack

- **Backend**: Django + Django REST Framework
- **Frontend**: Django Templates (Python-rendered HTML)
- **Database**: SQLite (Django ORM) with Firebase optional integration
- **Authentication**: Django built-in authentication system
- **Admin**: Django admin panel

## ✨ Features

✅ **Dashboard** - Overview of all metrics and statistics  
✅ **Client Management** - Create, edit, delete, and manage ISP clients  
✅ **Application Processing** - Handle new ISP service applications  
✅ **Support Tickets** - Track and manage customer support requests  
✅ **Payment Tracking** - Monitor and verify customer payments  
✅ **Search & Filter** - Find data quickly with powerful search  
✅ **REST API** - Full API endpoints for external integration  
✅ **Admin Panel** - Django admin for technical management  
✅ **Responsive Design** - Works on desktop and mobile  

## 🚀 Setup

### 1. Navigate to Backend Directory
```bash
cd backend
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Run Migrations
```bash
python manage.py migrate
```

### 6. Create Admin User
```bash
python manage.py createsuperuser
# Username: admin
# Password: password
```

### 7. Load Initial Data
```bash
python manage.py load_initial_data
```

### 8. Start Server
```bash
python manage.py runserver
```

The system will be available at: **http://localhost:8000**

## 🔐 Login

**URL**: `http://localhost:8000/accounts/login/`

**Default Credentials**:
- Username: `admin`
- Password: `password`

## 🌐 Access Points

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | Dashboard |
| `http://localhost:8000/clients/` | Client Management |
| `http://localhost:8000/applications/` | Applications |
| `http://localhost:8000/tickets/` | Support Tickets |
| `http://localhost:8000/payments/` | Payment Tracking |
| `http://localhost:8000/admin/` | Django Admin Panel |
| `http://localhost:8000/api/` | REST API |

## 📋 Main Views

### Dashboard
- Summary statistics (active clients, overdue, applications, tickets, payments)
- Recent activity (latest clients, tickets, applications, payments)
- Quick links to all sections

### Clients
- List all clients with status filtering
- Search by name, email, or phone
- Create new clients
- Edit client information
- View client details (payments, tickets, balance)
- Delete clients

### Applications
- View all service applications
- Filter by status (Pending, Approved, Declined)
- Create new applications
- Edit application details
- Track application progress

### Support Tickets
- List all support tickets
- Filter by status and priority
- Search by ticket ID, client, or category
- Create new tickets
- Assign tickets to technicians
- Track resolution progress
- Mark tickets as resolved

### Payments
- View all payment records
- Filter by payment status
- Search payments by ID or client
- Create new payment records
- Verify payment status
- Track payment history per client

## 🔌 REST API Endpoints

All endpoints require login. Access at `http://localhost:8000/api/`

### Clients
```
GET    /api/clients/              - List all clients
GET    /api/clients/<id>/         - Get client details
POST   /api/clients/              - Create client
PUT    /api/clients/<id>/         - Update client
DELETE /api/clients/<id>/         - Delete client
GET    /api/clients/active/       - Get active clients
GET    /api/clients/overdue/      - Get overdue clients
GET    /api/clients/?search=name  - Search clients
GET    /api/clients/?status=Active - Filter by status
```

### Applications
```
GET    /api/applications/         - List all
GET    /api/applications/<id>/    - Get details
POST   /api/applications/         - Create
PUT    /api/applications/<id>/    - Update
DELETE /api/applications/<id>/    - Delete
GET    /api/applications/pending/ - Pending only
```

### Tickets
```
GET    /api/tickets/              - List all
GET    /api/tickets/<id>/         - Get details
POST   /api/tickets/              - Create
PUT    /api/tickets/<id>/         - Update
DELETE /api/tickets/<id>/         - Delete
GET    /api/tickets/open_tickets/ - Open/In Progress
GET    /api/tickets/critical/     - Critical priority
```

### Payments
```
GET    /api/payments/             - List all
GET    /api/payments/<id>/        - Get details
POST   /api/payments/             - Create
PUT    /api/payments/<id>/        - Update
DELETE /api/payments/<id>/        - Delete
GET    /api/payments/pending/     - Pending only
GET    /api/payments/verified/    - Verified only
```

## Firebase Integration

Firebase credentials can be configured in `.env`:

```env
FIREBASE_API_KEY=your-key
FIREBASE_AUTH_DOMAIN=your-domain
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-bucket
FIREBASE_CREDENTIALS_PATH=./serviceAccountKey.json
```

Firebase Admin SDK is pre-configured in `firebase_service.py`.

## 🛠️ Admin Panel

Access Django admin at `http://localhost:8000/admin/`

Features:
- User management
- Database record editing
- Client, Application, Ticket, Payment CRUD
- Advanced filtering and search
- Bulk operations

## 🎨 Design & Styling

- Modern, clean UI
- Responsive sidebar navigation
- Color-coded status badges
- Forms with validation
- Mobile-friendly layout
- Smooth transitions and interactions

## 📱 Status Indicators

### Client Status
- 🟢 **Active** - Payment current
- 🔴 **Overdue** - Payment overdue
- ⚫ **Disconnected** - Service disconnected

### Application Status
- 🔵 **Pending** - Awaiting review
- 🟢 **Approved** - Approved for service
- 🔴 **Declined** - Application declined

### Ticket Status
- 🔴 **Open** - New ticket
- 🔵 **In Progress** - Being worked on
- 🟢 **Resolved** - Issue resolved
- ⚫ **Closed** - Ticket closed

### Ticket Priority
- 🟢 **Low** - Can wait
- 🟡 **Medium** - Normal handling
- 🟠 **High** - Urgent
- 🔴 **Critical** - Immediate action

### Payment Status
- 🔵 **Pending** - Awaiting verification
- 🟢 **Verified** - Confirmed
- 🔴 **Rejected** - Invalid payment

## 🔒 Security

- Django CSRF protection
- SQL injection prevention via ORM
- Password hashing
- Session-based authentication
- User permissions system
- Login required for all views

## 🐛 Troubleshooting

**"ModuleNotFoundError: No module named 'django'"**
```bash
pip install -r requirements.txt
```

**"Port 8000 already in use"**
```bash
python manage.py runserver 8001
```

**"No such table: api_client"**
```bash
python manage.py migrate
python manage.py load_initial_data
```

**Lost admin password**
```bash
python manage.py createsuperuser
```

## 📚 Project Structure

```
backend/
├── config/              # Django settings & URLs
├── api/                 # API models & serializers
├── dashboard/           # Frontend views & templates
│   ├── views.py         # All page views
│   ├── urls.py          # URL routing
│   └── templates/       # HTML templates
├── templates/           # Global templates (login)
├── manage.py            # Django CLI
├── requirements.txt     # Python dependencies
└── .env                 # Configuration
```

## ✅ Checklist

- [x] Full CRUD for all entities
- [x] Search and filtering
- [x] Dashboard with statistics
- [x] REST API
- [x] Admin panel
- [x] Django authentication
- [x] Responsive design
- [x] Firebase integration ready
- [x] Initial data loader
- [x] Error handling

## 🚀 Deployment

For production:

1. Update `SECRET_KEY` in `.env`
2. Set `DEBUG=False`
3. Configure allowed hosts
4. Use PostgreSQL instead of SQLite
5. Set up proper CORS headers
6. Configure Firebase credentials
7. Use gunicorn or similar WSGI server
8. Set up HTTPS

```bash
# Production command
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

---

**All original functionality and design preserved. Pure Python/Django implementation!** ✨
