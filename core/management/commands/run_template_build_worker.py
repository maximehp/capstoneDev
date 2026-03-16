import time
import threading

from django.conf import settings
from django.core.management.base import BaseCommand

from core.template_builds import (
    claim_next_queued_job,
    ensure_worker_runtime_ready,
    recover_stale_running_jobs,
    run_build_job,
)


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
        concurrency = max(1, int(getattr(settings, "TEMPLATE_BUILD_CONCURRENCY", 1)))

        checks = ensure_worker_runtime_ready()
        recovered = recover_stale_running_jobs()
        self.stdout.write(self.style.NOTICE("Template build worker started"))
        for check in checks:
            self.stdout.write(self.style.NOTICE(f"worker check ok: {check['check']}={check['value']}"))
        if recovered:
            self.stdout.write(self.style.WARNING(f"Recovered {recovered} stale running template build job(s)"))

        if run_once or concurrency == 1:
            self._worker_loop(run_once=run_once, sleep_seconds=sleep_seconds)
            return

        threads = []
        for index in range(concurrency):
            thread = threading.Thread(
                target=self._worker_loop,
                kwargs={"run_once": False, "sleep_seconds": sleep_seconds, "worker_name": f"slot-{index + 1}"},
                daemon=False,
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    def _worker_loop(self, run_once: bool, sleep_seconds: int, worker_name: str = "main"):
        while True:
            job = claim_next_queued_job()
            if not job:
                if run_once:
                    self.stdout.write(self.style.WARNING("No queued jobs"))
                    return
                time.sleep(max(1, sleep_seconds))
                continue

            self.stdout.write(self.style.NOTICE(f"[{worker_name}] Running job {job.uuid}"))
            run_build_job(job)

            if run_once:
                return
