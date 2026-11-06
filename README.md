# BizTrack - Business Analytics & Workflow Automation System
Flask web app to manage operational requests, track tasks, and automate workflow status updates, with SQL/pandas analytics, interactive dashboards, automated Excel reports and Power BI feeds.

**Stack:** Python · Flask · SQL (SQLite) · JavaScript (Chart.js) · Power BI · Excel (openpyxl)

## Quick start
```bash
pip install -r requirements.txt
python seed.py          # optional: 70 demo requests + tasks
python app.py           # http://127.0.0.1:5000
pytest                  # run tests
```

## Features
- **Request & task management** - create, filter, search; per-request task lists; full status history log.
- **Workflow engine** (`workflow.py`) - validated state machine (New -> In Progress -> On Hold/Completed/Cancelled; Completed can be reopened).
- **Automated status updates**
  - First task started -> request moves to *In Progress*
  - All tasks Done -> request auto-*Completed*
  - New/reopened task on a completed request -> auto-reopened
  - Overdue requests auto-escalate priority (1+ day -> High, 7+ days -> Critical); runs on dashboard load, via button, or `scheduled_report.py`
- **Data processing** (`analytics.py`) - SQL aggregations + pandas for KPIs (open, overdue, avg resolution, SLA %), trends, category and workload breakdowns.
- **Interactive Kanban Board** (`/kanban`) - Drag-and-drop workflow status updates across *New*, *In Progress*, *On Hold*, *Completed*, and *Cancelled* with real-time transition validation, subtask progress indicators, and toast notifications.
- **Interactive dashboard** - KPI cards + Chart.js charts fed by `/api/metrics`.
- **Automated Excel reporting** (`reports.py`) - multi-sheet workbook with native charts, filters, frozen headers; download from the UI, CLI (`python reports.py`) or cron (`scheduled_report.py`).
- **Power BI** - CSV feeds `/export/requests.csv`, `/export/tasks.csv`; see `powerbi/README.md`.

## Structure
```
app.py  workflow.py  analytics.py  reports.py  db.py  schema.sql
seed.py  scheduled_report.py  templates/  static/  tests/  powerbi/
```

## REST endpoints
`GET /api/metrics` · `POST /api/requests/<id>/status` · `GET /reports/excel` · `GET /export/{requests|tasks}.csv` · `POST /automation/run`
