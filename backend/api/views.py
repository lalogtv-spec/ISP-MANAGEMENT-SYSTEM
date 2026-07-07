from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from datetime import date, timedelta
from .models import Client, Application, ApplicationDecision, Ticket, Payment
from .serializers import ClientSerializer, ApplicationSerializer, TicketSerializer, PaymentSerializer


def _get_plan_fee(plan):
    """Get the standard fee for a plan label."""
    plan_fees = {
        'Basic': 499.00,
        'Standard': 799.00,
        'Premium': 1299.00,
        'Basic 25Mbps': 499.00,
        'Standard 50Mbps': 799.00,
        'Premium 100Mbps': 1299.00,
    }
    return plan_fees.get(plan, 499.00)


def _create_or_update_client_from_application(app):
    """Create or sync the client record that corresponds to an approved application."""
    plan_fee = _get_plan_fee(app.plan)
    client_data = {
        'name': app.name,
        'email': app.email,
        'phone': app.phone,
        'address': app.address,
        'plan': app.plan,
        'fee': plan_fee,
        'status': 'Active',
        'due_date': date.today() + timedelta(days=30),
        'balance': plan_fee,
        'joined': date.today(),
    }

    client = Client.objects.filter(email=app.email).first()
    if client:
        for field, value in client_data.items():
            setattr(client, field, value)
        client.save()
        return client

    client_id = None
    counter = Client.objects.count() + 1
    while client_id is None:
        candidate = f'C{str(counter).zfill(3)}'
        if not Client.objects.filter(client_id=candidate).exists():
            client_id = candidate
        else:
            counter += 1

    return Client.objects.create(client_id=client_id, **client_data)


def _record_application_decision(app, status, reason=''):
    """Persist the latest review decision before the application is removed."""
    return ApplicationDecision.objects.update_or_create(
        app_id=app.app_id,
        defaults={
            'user': app.user,
            'name': app.name,
            'phone': app.phone,
            'email': app.email,
            'address': app.address,
            'plan': app.plan,
            'status': status,
            'reason': reason or '',
            'date': app.date,
        },
    )[0]


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'phone']
    lookup_field = 'client_id'

    @action(detail=False, methods=['get'])
    def active(self, request):
        clients = Client.objects.filter(status='Active')
        serializer = self.get_serializer(clients, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        clients = Client.objects.filter(status='Overdue')
        serializer = self.get_serializer(clients, many=True)
        return Response(serializer.data)


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'email']
    lookup_field = 'app_id'

    @action(detail=False, methods=['get'])
    def pending(self, request):
        applications = Application.objects.filter(status='Pending')
        serializer = self.get_serializer(applications, many=True)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """Handle application status updates"""
        old_status = self.get_object().status
        serializer.save()
        app = serializer.instance
        reason = (self.request.data.get('reason') or self.request.data.get('rejection_reason') or '').strip()
        
        # Move approved applications into the client list, then remove the application.
        if old_status != 'Approved' and app.status == 'Approved':
            _create_or_update_client_from_application(app)
            _record_application_decision(app, 'Approved')
            app.delete()
            return

        # Rejected applications should not stay in the applications queue.
        if old_status != 'Declined' and app.status == 'Declined':
            _record_application_decision(app, 'Declined', reason=reason)
            app.delete()


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'priority']
    search_fields = ['ticket_id', 'client', 'category']
    lookup_field = 'ticket_id'

    @action(detail=False, methods=['get'])
    def open_tickets(self, request):
        tickets = Ticket.objects.filter(status__in=['Pending', 'In Progress'])
        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def critical(self, request):
        tickets = Ticket.objects.filter(priority='Critical')
        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    search_fields = ['payment_id', 'client']
    lookup_field = 'payment_id'

    @action(detail=False, methods=['get'])
    def pending(self, request):
        payments = Payment.objects.filter(status='Pending')
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def verified(self, request):
        payments = Payment.objects.filter(status='Verified')
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)
