"""Automated Excel reporting (openpyxl) - run via web UI, CLI, or scheduler."""
import io
import sys
from datetime import datetime
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import analytics

HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
HEAD_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="D0D7DE")


def _write_table(ws, df, start_row=1, start_col=1):
    for j, col in enumerate(df.columns):
        c = ws.cell(row=start_row, column=start_col + j, value=str(col).replace("_", " ").title())
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(horizontal="center")
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, v in enumerate(row):
            v = None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
            c = ws.cell(row=start_row + i, column=start_col + j, value=v)
            c.border = Border(bottom=THIN)
    return start_row + len(df)


def _autosize(ws):
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(width + 3, 48)


def build_workbook(db):
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "BizTrack - Business Performance Report"
    ws["A1"].font = Font(size=16, bold=True, color="1F4E79")
    ws["A2"] = f"Generated {datetime.now():%Y-%m-%d %H:%M}"
    k = analytics.kpis(db)
    labels = [("Total requests", k["total"]), ("Open", k["open"]), ("Completed", k["completed"]),
              ("Overdue", k["overdue"]), ("Avg resolution (days)", k["avg_resolution_days"]),
              ("SLA compliance (%)", k["sla_compliance_pct"])]
    for i, (lab, val) in enumerate(labels, start=4):
        ws.cell(row=i, column=1, value=lab).font = Font(bold=True)
        ws.cell(row=i, column=2, value=val)

    status, cat = analytics.by_status(db), analytics.by_category(db)
    trend = analytics.monthly_trend(db)
    r0 = 12
    end_s = _write_table(ws, status, r0, 1)
    end_c = _write_table(ws, cat[["category", "total", "completed"]], r0, 4)
    end_t = _write_table(ws, trend, r0, 8)

    pie = PieChart(); pie.title = "Requests by Status"
    pie.add_data(Reference(ws, min_col=2, min_row=r0, max_row=end_s), titles_from_data=True)
    pie.set_categories(Reference(ws, min_col=1, min_row=r0 + 1, max_row=end_s))
    ws.add_chart(pie, "A" + str(end_t + 3))

    bar = BarChart(); bar.title = "Requests by Category"; bar.type = "col"
    bar.add_data(Reference(ws, min_col=5, max_col=6, min_row=r0, max_row=end_c), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=4, min_row=r0 + 1, max_row=end_c))
    ws.add_chart(bar, "F" + str(end_t + 3))

    line = LineChart(); line.title = "Monthly Created vs Completed"
    line.add_data(Reference(ws, min_col=9, max_col=10, min_row=r0, max_row=end_t), titles_from_data=True)
    line.set_categories(Reference(ws, min_col=8, min_row=r0 + 1, max_row=end_t))
    ws.add_chart(line, "L" + str(end_t + 3))
    _autosize(ws)

    for name, df in [("Requests", analytics.requests_flat(db)), ("Tasks", analytics.tasks_flat(db)),
                     ("By Category", cat), ("Workload", analytics.workload(db))]:
        s = wb.create_sheet(name)
        _write_table(s, df)
        s.freeze_panes = "A2"
        s.auto_filter.ref = s.dimensions
        _autosize(s)
    return wb


def report_bytes(db):
    buf = io.BytesIO()
    build_workbook(db).save(buf)
    buf.seek(0)
    return buf


if __name__ == "__main__":       # python reports.py [out.xlsx]
    from db import connect
    from app import create_app
    app = create_app()
    out = sys.argv[1] if len(sys.argv) > 1 else f"biztrack_report_{datetime.now():%Y%m%d}.xlsx"
    conn = connect(app.config["DATABASE"])
    build_workbook(conn).save(out)
    print("Saved", out)
