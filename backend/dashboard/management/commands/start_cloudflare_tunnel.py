"""
Start a Cloudflare Tunnel for the local Django app and print the public URL.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import socket
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


URL_PATTERN = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com', re.IGNORECASE)


class Command(BaseCommand):
    help = 'Start a Cloudflare Tunnel and print the public URL'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='http://127.0.0.1:8000', help='Local URL to expose')
        parser.add_argument('--wait-seconds', type=int, default=20, help='How long to wait for the URL to appear')

    def handle(self, *args, **options):
        cloudflared = self._find_cloudflared()
        if not cloudflared:
            raise CommandError('cloudflared executable not found.')

        tunnel_url = str(options['url']).strip() or 'http://127.0.0.1:8000'
        wait_seconds = max(5, int(options['wait_seconds'] or 20))
        public_hostname = os.environ.get('PUBLIC_HOSTNAME', '').strip() or getattr(settings, 'PUBLIC_HOSTNAME', '').strip()
        tunnel_name = os.environ.get('CLOUDFLARED_TUNNEL_NAME', '').strip() or getattr(settings, 'CLOUDFLARED_TUNNEL_NAME', '').strip()

        self._ensure_local_server(tunnel_url)

        args = [cloudflared, 'tunnel']
        if tunnel_name:
            args.extend(['--name', tunnel_name])
        if public_hostname:
            args.extend(['--hostname', public_hostname])
        args.extend(['--url', tunnel_url])

        log_path = Path(settings.BASE_DIR) / 'cloudflared.admin.log'
        url_path = Path(settings.BASE_DIR) / 'cloudflared.current_url.txt'
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

        with log_path.open('w', encoding='utf-8', errors='ignore') as log_handle:
            subprocess.Popen(
                args,
                cwd=str(settings.BASE_DIR),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )

        resolved_url = ''
        if public_hostname:
            resolved_url = f'https://{public_hostname}'
        else:
            deadline = time.time() + wait_seconds
            while time.time() < deadline and not resolved_url:
                try:
                    log_text = log_path.read_text(encoding='utf-8', errors='ignore')
                except OSError:
                    log_text = ''
                match = URL_PATTERN.search(log_text)
                if match:
                    resolved_url = match.group(0)
                    break
                time.sleep(1)

        if not resolved_url:
            raise CommandError(
                'Cloudflare Tunnel started, but the public URL was not detected yet. '
                f'Check {log_path} for details.'
            )

        try:
            url_path.write_text(resolved_url, encoding='utf-8')
        except OSError:
            pass

        self.stdout.write(self.style.SUCCESS(f'Cloudflare tunnel started: {resolved_url}'))
        self.stdout.write(self.style.SUCCESS(f'Log file: {log_path}'))

    def _find_cloudflared(self):
        candidates = [
            shutil.which('cloudflared'),
            r'C:\Program Files (x86)\cloudflared\cloudflared.exe',
            r'C:\Program Files\cloudflared\cloudflared.exe',
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return ''

    def _ensure_local_server(self, tunnel_url):
        if self._is_port_open('127.0.0.1', 8000):
            return

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        subprocess.Popen(
            [
                sys.executable,
                'manage.py',
                'runserver',
                '127.0.0.1:8000',
                '--noreload',
            ],
            cwd=str(settings.BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            if self._is_port_open('127.0.0.1', 8000):
                return
            time.sleep(1)

        raise CommandError(f'Could not start the local server for {tunnel_url}.')

    @staticmethod
    def _is_port_open(host, port):
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False
