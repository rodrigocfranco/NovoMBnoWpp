"""Management command para checagem periódica de thresholds (Cloud Scheduler)."""

import sys

import structlog
from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from workflows.services.alerting import AlertingService
from workflows.services.metrics import MetricsService

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Check quality metrics against configured thresholds and emit alerts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show metrics summary without triggering alerts",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            summary = async_to_sync(MetricsService.get_metrics_summary)()
            self.stdout.write(self.style.SUCCESS("=== Metrics Summary ==="))
            for key, value in summary.items():
                self.stdout.write(f"  {key}: {value}")
            return

        alerts = async_to_sync(AlertingService.run_all_checks)()

        if alerts:
            for alert in alerts:
                self.stdout.write(self.style.ERROR(f"ALERT: {alert['type']}"))
                for key, value in alert.items():
                    if key != "type":
                        self.stdout.write(f"  {key}: {value}")
            logger.info("check_alerts_completed", alerts_triggered=len(alerts))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS("All metrics within thresholds."))
            logger.info("check_alerts_completed", alerts_triggered=0)
