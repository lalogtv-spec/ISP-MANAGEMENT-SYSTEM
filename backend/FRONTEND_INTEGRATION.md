"""
Integration guide for connecting React frontend to Django backend
"""

# FRONTEND INTEGRATION STEPS

## 1. Create API service file in React

# src/services/api.ts
```typescript
const API_URL = 'http://localhost:8000/api';

export const api = {
  // Clients
  getClients: () => fetch(`${API_URL}/clients/`).then(r => r.json()),
  getClient: (id: string) => fetch(`${API_URL}/clients/${id}/`).then(r => r.json()),
  createClient: (data: any) => fetch(`${API_URL}/clients/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),
  updateClient: (id: string, data: any) => fetch(`${API_URL}/clients/${id}/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),
  deleteClient: (id: string) => fetch(`${API_URL}/clients/${id}/`, {
    method: 'DELETE'
  }),

  // Applications
  getApplications: () => fetch(`${API_URL}/applications/`).then(r => r.json()),
  getPendingApplications: () => fetch(`${API_URL}/applications/pending/`).then(r => r.json()),
  createApplication: (data: any) => fetch(`${API_URL}/applications/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),

  // Tickets
  getTickets: () => fetch(`${API_URL}/tickets/`).then(r => r.json()),
  getCriticalTickets: () => fetch(`${API_URL}/tickets/critical/`).then(r => r.json()),
  createTicket: (data: any) => fetch(`${API_URL}/tickets/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),
  updateTicket: (id: string, data: any) => fetch(`${API_URL}/tickets/${id}/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),

  // Payments
  getPayments: () => fetch(`${API_URL}/payments/`).then(r => r.json()),
  getPendingPayments: () => fetch(`${API_URL}/payments/pending/`).then(r => r.json()),
  verifyPayment: (id: string) => fetch(`${API_URL}/payments/${id}/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'Verified' })
  }).then(r => r.json()),
};
```

## 2. Update React components to use API

# Example: Replace static data with API calls in App.tsx

```typescript
// Before
const CLIENTS = [{ id: "C001", name: "Maria Santos", ... }];

// After
const [clients, setClients] = useState([]);

useEffect(() => {
  api.getClients().then(data => setClients(data.results || data));
}, []);
```

## 3. Handle loading and error states

```typescript
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);

const fetchClients = async () => {
  setLoading(true);
  try {
    const data = await api.getClients();
    setClients(data.results || data);
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

## 4. Environment variables

# .env (in frontend root)
```
VITE_API_URL=http://localhost:8000/api
```

## 5. CORS Configuration

The Django backend is already configured for CORS. If you get CORS errors:

# backend/.env
```
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

Then restart Django:
```bash
python manage.py runserver
```

## 6. Running both frontend and backend

Terminal 1 - Django Backend:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_initial_data
python manage.py runserver
```

Terminal 2 - React Frontend:
```bash
npm run dev
```

Access the app at http://localhost:5173

## 7. Pagination

The API returns paginated results (10 per page):
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/clients/?page=2",
  "previous": null,
  "results": [...]
}
```

Handle pagination in React:
```typescript
const [page, setPage] = useState(1);

const fetchClients = (pageNum: number) => {
  api.getClients()
    .then(data => {
      setClients(data.results);
      setTotal(data.count);
    });
};
```

## 8. Filtering and Search

```typescript
// Filter by status
fetch(`${API_URL}/clients/?status=Active`)

// Search by name
fetch(`${API_URL}/clients/?search=Maria`)

// Multiple filters
fetch(`${API_URL}/tickets/?status=Open&priority=Critical`)
```

## 9. Firebase Authentication (Optional)

If using Firebase auth in React:

```typescript
const handleLogin = async (email, password) => {
  const userCred = await signInWithEmailAndPassword(auth, email, password);
  const idToken = await userCred.user.getIdToken();
  
  // Send to backend
  const response = await fetch(`${API_URL}/auth/verify-token/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${idToken}`
    },
    body: JSON.stringify({ idToken })
  });
};
```

## 10. Troubleshooting

**CORS Error**
- Ensure frontend URL is in CORS_ALLOWED_ORIGINS
- Restart Django server

**API Not Found (404)**
- Check that Django is running on port 8000
- Verify endpoint matches router configuration in urls.py

**Data Not Loading**
- Check browser Network tab for API response
- Look for validation errors in Django error logs

**Port Already in Use**
- Kill process: `npx kill-port 8000` (backend) or `npx kill-port 5173` (frontend)
- Or specify different port: `python manage.py runserver 8001`
