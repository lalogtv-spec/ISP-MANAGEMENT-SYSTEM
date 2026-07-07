from rest_framework import serializers
from .models import Client, Application, Ticket, Payment


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            'client_id', 'name', 'address', 'phone', 'email', 
            'plan', 'fee', 'status', 'due_date', 'balance', 'joined'
        ]


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = [
            'app_id', 'name', 'phone', 'email', 'address',
            'latitude', 'longitude', 'plan', 'status', 'date'
        ]


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'client', 'category', 'priority', 'status', 
            'description', 'assigned', 'created'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'payment_id', 'client', 'date', 'amount', 'period', 
            'method', 'status'
        ]
