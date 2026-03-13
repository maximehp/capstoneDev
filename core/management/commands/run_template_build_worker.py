import time

from django.conf import settings
from django.core.management.base import BaseCommand

from core.template_builds import claim_next_queued_job, run_build_job


class Command(BaseCommand):
    help = "Runs the background worker that executes queued template build jobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one queued job and exit.",
        )
        parser.add_argument(
            "--sleep",
            type=int,
            default=None,
            help="Sleep interval in seconds when queue is empty.",
        )

    def handle(self, *args, **options):
        run_once = bool(options.get("once"))
        sleep_seconds = int(options.get("sleep") or settings.TEMPLATE_BUILD_POLL_SECONDS)

        self.stdout.write(self.style.NOTICE("Template build worker started"))

        while True:
            job = claim_next_queued_job()
            if not job:
                if run_once:
                    self.stdout.write(self.style.WARNING("No queued jobs"))
                    return
                time.sleep(max(1, sleep_seconds))
                continue

            self.stdout.write(self.style.NOTICE(f"Running job {job.uuid}"))
            run_build_job(job)

            if run_once:
                return
