#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _project_python():
    """Prefer the project virtualenv so `py manage.py ...` still works."""
    manage_dir = Path(__file__).resolve().parent
    project_root = manage_dir.parent
    candidates = [
        project_root / '.venv' / 'Scripts' / 'python.exe',
        manage_dir / 'venv' / 'Scripts' / 'python.exe',
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    project_python = _project_python()
    if project_python and os.path.abspath(sys.executable).lower() != os.path.abspath(project_python).lower():
        os.execv(project_python, [project_python, __file__, *sys.argv[1:]])
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
