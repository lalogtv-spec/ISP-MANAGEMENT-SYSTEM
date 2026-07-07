#!/bin/bash
# Django Backend Setup Script for macOS/Linux

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running migrations..."
python manage.py migrate

echo "Loading initial data..."
python manage.py load_initial_data

echo ""
echo "Setup complete! Run these commands to start:"
echo ""
echo "1. Activate venv: source venv/bin/activate"
echo "2. Start server: python manage.py runserver"
echo ""
echo "Access the API at: http://localhost:8000/api/"
echo "Admin panel at: http://localhost:8000/admin/"
echo ""
