# PythonAnywhere Deployment Guide

This repository is ready to deploy to PythonAnywhere, but I cannot complete the deployment on your PythonAnywhere account from this environment.

## Prerequisites
1. A PythonAnywhere account.
2. GitHub access to `https://github.com/lalogtv-spec/ISP-MANAGEMENT-SYSTEM`.
3. Python 3.12 available on PythonAnywhere.

## Steps

### 1. Create the web app
1. Log in to PythonAnywhere.
2. Go to the **Web** tab.
3. Create a new web app.
4. Choose **Manual configuration**.
5. Select **Python 3.12**.

### 2. Clone the repository
Open a Bash console on PythonAnywhere and run:

```bash
cd ~/
git clone https://github.com/lalogtv-spec/ISP-MANAGEMENT-SYSTEM.git
cd ISP-MANAGEMENT-SYSTEM/backend
```

If the repo is already cloned, just `cd ~/ISP-MANAGEMENT-SYSTEM/backend`.

### 3. Install dependencies

```bash
python3.12 -m pip install --user --no-cache-dir -r requirements-pythonanywhere.txt
rm -rf ~/.cache/pip /tmp/pip-* 2>/dev/null || true
```

If any package fails, note the error and we can adjust the requirements.

> PythonAnywhere free accounts have a strict disk quota. If you hit `disk quota exceeded` while installing, use the above command and remove cached files.
>
> The install may still fail if you try to install heavy machine-learning packages from `backend/requirements.txt`, such as `opencv-python`, `onnxruntime`, `tensorflow`, `deepface`, and `keras`.
>
> This `requirements-pythonanywhere.txt` file installs only the core Django dependencies and should fit on a free account.
>
> If you need face authentication or advanced biometric features, install those extra packages only after the core app is running.
>
> If you need the full ML feature set, use a paid PythonAnywhere plan or deploy to a host with more disk space.

### 4. Configure environment variables

PythonAnywhere web apps can set environment variables in the **Web** tab under "Environment variables".

Set at least:

- `SECRET_KEY` = a strong secret string
- `DEBUG` = `False`
- `ALLOWED_HOSTS` = `yourusername.pythonanywhere.com`
- `PUBLIC_HOSTNAME` = `yourusername.pythonanywhere.com`
- `CORS_ALLOWED_ORIGINS` = `https://yourusername.pythonanywhere.com`

If you use any external services, also set keys for those services.

### 5. Configure the WSGI file

In the PythonAnywhere **Web** tab, set the WSGI configuration to point to the Django app.

Edit the WSGI file so it contains:

```python
import os
import sys

path = '/home/yourusername/ISP-MANAGEMENT-SYSTEM/backend'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Replace `yourusername` with your PythonAnywhere username.

### 6. Set the source path

Also in the **Web** tab, make sure the source folder is:

```
/home/yourusername/ISP-MANAGEMENT-SYSTEM/backend
```

### 7. Collect static files

Run this in the Bash console:

```bash
cd ~/ISP-MANAGEMENT-SYSTEM/backend
python3.12 manage.py collectstatic --noinput
```

### 8. Run migrations

```bash
cd ~/ISP-MANAGEMENT-SYSTEM/backend
python3.12 manage.py migrate
```

### 9. Reload the web app

In the PythonAnywhere **Web** tab, click **Reload**.

### 10. Verify the site

Open `https://yourusername.pythonanywhere.com` in your browser.

## Notes

- This project uses SQLite (`backend/db.sqlite3`), which is supported on PythonAnywhere.
- `STATIC_ROOT` is already set to `BASE_DIR / 'staticfiles'`.
- `MEDIA_ROOT` is set to `BASE_DIR / 'media'`.
- If the deploy fails due to heavy packages like `opencv-python` or `onnxruntime`, the environment may need extra setup or a different hosting option.

## Help
If you get an error during install, migration, or reload, copy the exact console error and I can help fix it.
