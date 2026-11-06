# Power BI setup

BizTrack exposes BI-ready feeds while the app is running (`python app.py`):

| Feed | URL |
|---|---|
| Requests (denormalised, with `resolution_days`, `is_overdue`, `met_sla`) | `http://127.0.0.1:5000/export/requests.csv` |
| Tasks | `http://127.0.0.1:5000/export/tasks.csv` |
| Full workbook | `http://127.0.0.1:5000/reports/excel` |

## Steps
1. Power BI Desktop -> **Get data -> Web** -> paste the requests URL; repeat for tasks.
2. Model: relate `Tasks[request_id]` -> `Requests[request_id]` (many-to-one).
3. Suggested measures (DAX):

```
Total Requests = COUNTROWS(Requests)
Open Requests  = CALCULATE([Total Requests], Requests[status] IN {"New","In Progress","On Hold"})
Overdue        = SUM(Requests[is_overdue])
Avg Resolution Days = AVERAGE(Requests[resolution_days])
SLA % = DIVIDE(CALCULATE(COUNTROWS(Requests), Requests[met_sla] = 1), CALCULATE(COUNTROWS(Requests), NOT ISBLANK(Requests[met_sla])))
```
4. Visuals: KPI cards, line chart (created_at by month), donut (status), stacked bar (category x status), table of overdue requests.
5. Refresh: Home -> Refresh, or schedule via the Power BI gateway.
