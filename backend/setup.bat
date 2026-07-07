@echo off
REM Django Backend Setup Script for Windows

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo Running migrations...
python manage.py migrate

echo Loading initial data...
python manage.py load_initial_data

echo.
echo Setup complete! Run these commands to start:
echo.
echo 1. Activate venv: venv\Scripts\activate.bat
echo 2. Start server: python manage.py runserver
echo.
echo Access the API at: http://localhost:8000/api/
echo Admin panel at: http://localhost:8000/admin/
echo.
pause
