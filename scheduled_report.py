"""Run nightly (cron / Windows Task Scheduler): escalates overdue work and saves an Excel report.
   cron:  0 7 * * *  cd /path/to/biztrack && python scheduled_report.py"""
import os
from datetime import datetime
from app import create_app
from db import connect
import reports, workflow as wf

app = create_app()
conn = connect(app.config["DATABASE"])
n = wf.escalate_overdue(conn)
os.makedirs("reports_out", exist_ok=True)
out = f"reports_out/biztrack_{datetime.now():%Y%m%d}.xlsx"
reports.build_workbook(conn).save(out)
print(f"{n} escalated; report saved to {out}")
