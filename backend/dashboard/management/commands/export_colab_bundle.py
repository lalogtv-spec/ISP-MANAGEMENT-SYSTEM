"""
Export a Colab-ready bundle for face analysis and payment/overdue analysis.

The bundle includes:
- clients.csv
- payments.csv
- overdue_snapshot.csv
- facial_biometrics.jsonl
- summary.json

Usage:
    python manage.py export_colab_bundle
    python manage.py export_colab_bundle --output C:\\tmp\\colab_bundle.zip
"""

from __future__ import annotations

import csv
import json
import zipfile
import shutil
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Client, Payment
from security.models import BiometricData, UserSecurityProfile


@dataclass
class ExportFile:
    path: Path
    name: str


class Command(BaseCommand):
    help = "Export a Colab-ready bundle for face and payment analytics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="",
            help="Optional zip file path. If omitted, writes to the Colab export directory.",
        )
        parser.add_argument(
            "--include-models",
            action="store_true",
            help="Include model-friendly JSONL exports for biometric analysis.",
        )

    def handle(self, *args, **options):
        include_models = options["include_models"]
        export_root = Path(settings.COLAB_EXPORT_DIR)
        export_root.mkdir(parents=True, exist_ok=True)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        bundle_dir = export_root / f"colab_bundle_{timestamp}"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        exported_files = [
            self._export_clients(bundle_dir),
            self._export_payments(bundle_dir),
            self._export_overdue_snapshot(bundle_dir),
            self._export_summary(bundle_dir),
        ]
        if include_models:
            exported_files.append(self._export_facial_biometrics(bundle_dir))
            exported_files.append(self._export_face_images(bundle_dir))

        output = str(options["output"] or "").strip()
        if output:
            zip_path = Path(output)
        else:
            zip_path = export_root / f"{bundle_dir.name}.zip"

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for export_file in exported_files:
                archive.write(export_file.path, arcname=export_file.name)

        self.stdout.write(self.style.SUCCESS(f"Exported Colab bundle to {zip_path}"))
        self.stdout.write(self.style.SUCCESS(f"Bundle directory: {bundle_dir}"))
        self.stdout.write(self.style.SUCCESS("Files included:"))
        for export_file in exported_files:
            self.stdout.write(f"  - {export_file.name}")

    def _export_clients(self, bundle_dir: Path) -> ExportFile:
        path = bundle_dir / "clients.csv"
        fields = [
            "client_id",
            "name",
            "email",
            "phone",
            "address",
            "plan",
            "fee",
            "status",
            "due_date",
            "balance",
            "joined",
            "days_overdue",
        ]
        today = timezone.localdate()

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for client in Client.objects.all().order_by("client_id"):
                due_date = client.due_date
                days_overdue = max(0, (today - due_date).days) if due_date else 0
                writer.writerow(
                    {
                        "client_id": client.client_id,
                        "name": client.name,
                        "email": client.email,
                        "phone": client.phone,
                        "address": client.address,
                        "plan": client.plan,
                        "fee": str(client.fee),
                        "status": client.status,
                        "due_date": due_date.isoformat() if due_date else "",
                        "balance": str(client.balance),
                        "joined": client.joined.isoformat() if client.joined else "",
                        "days_overdue": days_overdue,
                    }
                )
        return ExportFile(path=path, name=path.name)

    def _export_payments(self, bundle_dir: Path) -> ExportFile:
        path = bundle_dir / "payments.csv"
        fields = [
            "payment_id",
            "client",
            "date",
            "amount",
            "period",
            "method",
            "status",
        ]

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for payment in Payment.objects.all().order_by("-date", "-created_at"):
                writer.writerow(
                    {
                        "payment_id": payment.payment_id,
                        "client": payment.client,
                        "date": payment.date.isoformat() if payment.date else "",
                        "amount": str(payment.amount),
                        "period": payment.period,
                        "method": payment.method,
                        "status": payment.status,
                    }
                )
        return ExportFile(path=path, name=path.name)

    def _export_overdue_snapshot(self, bundle_dir: Path) -> ExportFile:
        path = bundle_dir / "overdue_snapshot.csv"
        fields = [
            "client_id",
            "name",
            "status",
            "due_date",
            "balance",
            "days_overdue",
            "risk_bucket",
        ]
        today = timezone.localdate()

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for client in Client.objects.exclude(status="Active").order_by("-updated_at"):
                days_overdue = max(0, (today - client.due_date).days) if client.due_date else 0
                risk_bucket = "critical" if days_overdue >= 4 or client.status == "Disconnected" else "warning"
                writer.writerow(
                    {
                        "client_id": client.client_id,
                        "name": client.name,
                        "status": client.status,
                        "due_date": client.due_date.isoformat() if client.due_date else "",
                        "balance": str(client.balance),
                        "days_overdue": days_overdue,
                        "risk_bucket": risk_bucket,
                    }
                )
        return ExportFile(path=path, name=path.name)

    def _export_facial_biometrics(self, bundle_dir: Path) -> ExportFile:
        path = bundle_dir / "facial_biometrics.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            records = BiometricData.objects.filter(biometric_type="facial", is_active=True).select_related("user")
            for biometric in records:
                profile = None
                try:
                    profile = UserSecurityProfile.objects.get(user=biometric.user)
                except UserSecurityProfile.DoesNotExist:
                    profile = None
                try:
                    template = json.loads(biometric.template_data)
                except Exception:
                    template = {"template_data": biometric.template_data}
                payload = {
                    "user_id": biometric.user_id,
                    "username": biometric.user.username,
                    "email": biometric.user.email,
                    "facial_data_enrolled": bool(profile and profile.facial_data_enrolled),
                    "enrolled_at": biometric.enrolled_at.isoformat() if biometric.enrolled_at else None,
                    "quality_score": biometric.enrollment_quality_score,
                    "confidence": biometric.enrollment_confidence,
                    "template": template,
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return ExportFile(path=path, name=path.name)

    def _export_face_images(self, bundle_dir: Path) -> ExportFile:
        manifest_path = bundle_dir / "face_images_manifest.csv"
        images_dir = bundle_dir / "face_images"
        images_dir.mkdir(parents=True, exist_ok=True)
        fields = [
            "user_id",
            "username",
            "biometric_id",
            "sample_image_file",
            "quality_score",
            "confidence",
            "enrolled_at",
        ]
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            records = BiometricData.objects.filter(
                biometric_type="facial",
                is_active=True,
            ).select_related("user")
            for biometric in records:
                if not biometric.sample_image_path:
                    continue
                source_path = Path(biometric.sample_image_path)
                if not source_path.exists():
                    continue
                target_name = f"{biometric.user_id}_{biometric.id}_{source_path.name}"
                target_path = images_dir / target_name
                shutil.copy2(source_path, target_path)
                writer.writerow(
                    {
                        "user_id": biometric.user_id,
                        "username": biometric.user.username,
                        "biometric_id": biometric.id,
                        "sample_image_file": str(Path("face_images") / target_name),
                        "quality_score": biometric.enrollment_quality_score,
                        "confidence": biometric.enrollment_confidence,
                        "enrolled_at": biometric.enrolled_at.isoformat() if biometric.enrolled_at else "",
                    }
                )
        return ExportFile(path=manifest_path, name=manifest_path.name)

    def _export_summary(self, bundle_dir: Path) -> ExportFile:
        path = bundle_dir / "summary.json"
        clients = list(Client.objects.all())
        payments = list(Payment.objects.all())
        overdue_clients = [client for client in clients if client.status == "Overdue"]
        disconnected_clients = [client for client in clients if client.status == "Disconnected"]
        active_clients = [client for client in clients if client.status == "Active"]
        summary = {
            "exported_at": datetime.now().isoformat(),
            "client_count": len(clients),
            "payment_count": len(payments),
            "overdue_client_count": len(overdue_clients),
            "disconnected_client_count": len(disconnected_clients),
            "active_client_count": len(active_clients),
            "face_template_count": BiometricData.objects.filter(biometric_type="facial", is_active=True).count(),
            "overdue_balance_total": str(
                sum((client.balance for client in overdue_clients), start=Decimal("0"))
            ),
            "generated_by": "export_colab_bundle",
        }
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return ExportFile(path=path, name=path.name)
