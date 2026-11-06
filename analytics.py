"""Data processing: SQL aggregation + pandas shaping for dashboard, Excel and Power BI."""
import pandas as pd
from workflow import OPEN

_OPEN_SQL = "('" + "','".join(OPEN) + "')"


def frame(db, sql, params=()):
    return pd.read_sql_query(sql, db, params=params)


def kpis(db):
    r = db.execute(f"""
        SELECT COUNT(*) AS total,
               COALESCE(SUM(status IN {_OPEN_SQL}), 0) AS open_count,
               COALESCE(SUM(status = 'Completed'), 0) AS completed,
               COALESCE(SUM(status IN {_OPEN_SQL} AND due_date < date('now')), 0) AS overdue
        FROM requests""").fetchone()
    avg = db.execute("SELECT AVG(julianday(closed_at) - julianday(created_at)) FROM requests "
                     "WHERE status='Completed'").fetchone()[0]
    sla = db.execute("SELECT 100.0 * SUM(date(closed_at) <= due_date) / COUNT(*) FROM requests "
                     "WHERE status='Completed'").fetchone()[0]
    return {"total": r["total"], "open": r["open_count"], "completed": r["completed"],
            "overdue": r["overdue"], "avg_resolution_days": round(avg or 0, 1),
            "sla_compliance_pct": round(sla or 0, 1)}


def by_status(db):
    return frame(db, "SELECT status, COUNT(*) AS count FROM requests GROUP BY status")


def by_category(db):
    return frame(db, f"""SELECT category, COUNT(*) AS total,
        SUM(status IN {_OPEN_SQL}) AS open_count, SUM(status='Completed') AS completed,
        ROUND(AVG(CASE WHEN status='Completed' THEN julianday(closed_at)-julianday(created_at) END),1) AS avg_days
        FROM requests GROUP BY category ORDER BY total DESC""")


def by_priority(db):
    return frame(db, "SELECT priority, COUNT(*) AS count FROM requests GROUP BY priority")


def workload(db):
    return frame(db, """SELECT assignee, COUNT(*) AS total,
        SUM(status='Done') AS done, SUM(status!='Done') AS pending
        FROM tasks GROUP BY assignee ORDER BY pending DESC""")


def monthly_trend(db):
    created = frame(db, "SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS created "
                        "FROM requests GROUP BY month")
    closed = frame(db, "SELECT strftime('%Y-%m', closed_at) AS month, COUNT(*) AS completed "
                       "FROM requests WHERE status='Completed' GROUP BY month")
    out = created.merge(closed, on="month", how="outer").fillna(0).sort_values("month")
    out[["created", "completed"]] = out[["created", "completed"]].astype(int)
    return out


def requests_flat(db):
    """Denormalised, BI-friendly table (also used for Power BI)."""
    df = frame(db, """SELECT r.id AS request_id, r.title, r.category, r.priority, r.status, r.requester,
        r.department, r.created_at, r.due_date, r.closed_at,
        COUNT(t.id) AS task_count, COALESCE(SUM(t.status='Done'),0) AS tasks_done
        FROM requests r LEFT JOIN tasks t ON t.request_id = r.id GROUP BY r.id""")
    created = pd.to_datetime(df["created_at"])
    closed = pd.to_datetime(df["closed_at"])
    df["resolution_days"] = ((closed - created).dt.total_seconds() / 86400).round(1)
    df["is_overdue"] = ((df["status"].isin(OPEN)) & (pd.to_datetime(df["due_date"]) < pd.Timestamp.now().normalize())).astype(int)
    df["met_sla"] = (closed.dt.normalize() <= pd.to_datetime(df["due_date"])).astype("Int64").where(closed.notna())
    return df


def tasks_flat(db):
    return frame(db, """SELECT t.id AS task_id, t.request_id, r.category, t.title, t.assignee, t.status,
        t.due_date, t.created_at, t.completed_at FROM tasks t JOIN requests r ON r.id = t.request_id""")


def metrics(db):
    return {"kpis": kpis(db),
            "by_status": by_status(db).to_dict("records"),
            "by_category": by_category(db).to_dict("records"),
            "by_priority": by_priority(db).to_dict("records"),
            "workload": workload(db).to_dict("records"),
            "trend": monthly_trend(db).to_dict("records")}
