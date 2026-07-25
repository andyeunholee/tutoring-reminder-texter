"""Subprocess entrypoint for sending SMS jobs.

Usage: python sms_job_runner.py <config.json>

Config: {"dry_run": bool, "user_data_dir": str, "delay_between_jobs": float,
         "screenshot_dir": str, "jobs": [{id, label, recipients, group_mode, message}]}

Stdout protocol (one line each, UTF-8, flushed):
  PROGRESS:<free text>
  JOBSTART:{"id":..., "index":1, "total":10}
  JOBRESULT:{"id":..., "status":"sent|dry_run|failed|skipped", "error":...}
  DONE:{"sent":8, "dry_run":0, "failed":1, "skipped":1}
  ERROR_TRACE:<traceback>
"""

import io
import json
import os
import sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from sms import gv_sender  # noqa: E402


def emit(line: str):
    print(line)
    sys.stdout.flush()


def run():
    try:
        if len(sys.argv) < 2:
            emit("PROGRESS:Error: config path argument missing")
            return

        with open(sys.argv[1], "r", encoding="utf-8") as f:
            config = json.load(f)

        jobs = config.get("jobs", [])
        total = len(jobs)

        def progress(msg):
            emit(f"PROGRESS:{msg}")

        def on_start(i, job):
            emit("JOBSTART:" + json.dumps(
                {"id": job["id"], "index": i + 1, "total": total}))

        def on_result(i, job, result):
            emit("JOBRESULT:" + json.dumps(result, ensure_ascii=False))

        results = gv_sender.run_jobs(
            jobs,
            progress_callback=progress,
            dry_run=config.get("dry_run", False),
            user_data_dir=config.get("user_data_dir"),
            delay_between=float(config.get("delay_between_jobs", 4.0)),
            screenshot_dir=config.get("screenshot_dir"),
            browser_channel=config.get("browser_channel", "chrome"),
            on_job_start=on_start,
            on_job_result=on_result,
        )

        summary = {"sent": 0, "dry_run": 0, "failed": 0, "skipped": 0}
        for r in results:
            summary[r["status"]] = summary.get(r["status"], 0) + 1
        emit("DONE:" + json.dumps(summary))

    except Exception:
        emit("PROGRESS:Critical error in SMS subprocess")
        emit("ERROR_TRACE:" + traceback.format_exc().replace("\n", " | "))


if __name__ == "__main__":
    run()
