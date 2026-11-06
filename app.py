"""BizTrack - Flask application."""
import os
from datetime import date, timedelta
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, send_file, Response, abort)
import analytics
import reports
import workflow as wf
from db import get_db, close_db, connect, init_schema, now, ROOT


def create_app(config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
    app.config["DATABASE"] = os.environ.get("BIZTRACK_DB", os.path.join(ROOT, "instance", "biztrack.db"))
    if config:
        app.config.update(config)
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    if not os.path.exists(app.config["DATABASE"]):
        conn = connect(app.config["DATABASE"]); init_schema(conn); conn.close()
    app.teardown_appcontext(close_db)

    app.jinja_env.globals.update(
        STATUSES=wf.REQUEST_STATUSES, TASK_STATUSES=wf.TASK_STATUSES,
        PRIORITIES=wf.PRIORITIES, CATEGORIES=wf.CATEGORIES, TRANSITIONS=wf.TRANSITIONS,
        today=lambda: date.today().isoformat())

    @app.template_filter("slug")
    def slug(s):
        return str(s).lower().replace(" ", "-")

    @app.route("/")
    def dashboard():
        db = get_db()
        wf.escalate_overdue(db)
        recent = db.execute("SELECT * FROM requests ORDER BY updated_at DESC LIMIT 6").fetchall()
        return render_template("dashboard.html", k=analytics.kpis(db), recent=recent)

    @app.route("/requests")
    def requests_list():
        db = get_db()
        status, priority, category, q = (request.args.get(x, "") for x in ("status", "priority", "category", "q"))
        sql, args = "SELECT * FROM requests WHERE 1=1", []
        for col, val in (("status", status), ("priority", priority), ("category", category)):
            if val:
                sql += f" AND {col}=?"; args.append(val)
        if q:
            sql += " AND (title LIKE ? OR requester LIKE ?)"; args += [f"%{q}%"] * 2
        sql += " ORDER BY CASE priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, due_date"
        return render_template("requests.html", rows=db.execute(sql, args).fetchall(),
                               f=dict(status=status, priority=priority, category=category, q=q))

    @app.route("/kanban")
    def kanban():
        db = get_db()
        priority, category, q = (request.args.get(x, "") for x in ("priority", "category", "q"))
        sql = """
            SELECT r.*,
                   COUNT(t.id) AS task_count,
                   SUM(CASE WHEN t.status = 'Done' THEN 1 ELSE 0 END) AS task_done_count
            FROM requests r
            LEFT JOIN tasks t ON t.request_id = r.id
            WHERE 1=1
        """
        args = []
        for col, val in (("r.priority", priority), ("r.category", category)):
            if val:
                sql += f" AND {col}=?"; args.append(val)
        if q:
            sql += " AND (r.title LIKE ? OR r.requester LIKE ?)"; args += [f"%{q}%"] * 2
        sql += " GROUP BY r.id ORDER BY CASE r.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, r.due_date"
        rows = db.execute(sql, args).fetchall()

        columns = {s: [] for s in wf.REQUEST_STATUSES}
        for r in rows:
            if r["status"] in columns:
                columns[r["status"]].append(r)

        return render_template("kanban.html", columns=columns,
                               f=dict(priority=priority, category=category, q=q),
                               transitions=wf.TRANSITIONS)

    @app.route("/requests/new", methods=["GET", "POST"])
    def request_new():
        if request.method == "POST":
            f = request.form
            title, requester, dept = f.get("title", "").strip(), f.get("requester", "").strip(), f.get("department", "").strip()
            due = f.get("due_date") or (date.today() + timedelta(days=7)).isoformat()
            if not (title and requester and dept) or f.get("category") not in wf.CATEGORIES \
                    or f.get("priority") not in wf.PRIORITIES:
                flash("Please fill in all required fields correctly.", "error")
                return render_template("request_new.html", f=f), 400
            db = get_db()
            cur = db.execute(
                "INSERT INTO requests(title, description, category, priority, requester, department, "
                "created_at, due_date, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (title, f.get("description", "").strip(), f["category"], f["priority"], requester, dept, now(), due, now()))
            wf.log(db, "request", cur.lastrowid, None, "New", "created")
            db.commit()
            flash("Request created.", "ok")
            return redirect(url_for("request_detail", rid=cur.lastrowid))
        return render_template("request_new.html", f={})

    @app.route("/requests/<int:rid>")
    def request_detail(rid):
        db = get_db()
        r = db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone() or abort(404)
        tasks = db.execute("SELECT * FROM tasks WHERE request_id=? ORDER BY id", (rid,)).fetchall()
        hist = db.execute("SELECT * FROM status_log WHERE entity='request' AND entity_id=? ORDER BY id DESC", (rid,)).fetchall()
        return render_template("request_detail.html", r=r, tasks=tasks, hist=hist)

    def _guard(fn, back):
        try:
            fn()
        except wf.WorkflowError as e:
            flash(str(e), "error")
        return redirect(back)

    @app.post("/requests/<int:rid>/status")
    def request_status(rid):
        return _guard(lambda: wf.set_request_status(get_db(), rid, request.form.get("status", ""), "manual"),
                      url_for("request_detail", rid=rid))

    @app.post("/api/requests/<int:rid>/status")
    def api_request_status(rid):
        data = request.get_json(silent=True) or request.form
        new_status = data.get("status")
        if not new_status:
            return jsonify({"ok": False, "error": "Status is required"}), 400
        try:
            res = wf.set_request_status(get_db(), rid, new_status, "kanban drag-and-drop")
            return jsonify({"ok": True, "status": res})
        except wf.WorkflowError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/requests/<int:rid>/tasks")
    def task_add(rid):
        f = request.form
        title, who = f.get("title", "").strip(), f.get("assignee", "").strip()
        if not (title and who):
            flash("Task title and assignee are required.", "error")
            return redirect(url_for("request_detail", rid=rid))
        return _guard(lambda: wf.add_task(get_db(), rid, title, who, f.get("due_date")),
                      url_for("request_detail", rid=rid))

    @app.post("/tasks/<int:tid>/status")
    def task_status(tid):
        db = get_db()
        t = db.execute("SELECT request_id FROM tasks WHERE id=?", (tid,)).fetchone() or abort(404)
        return _guard(lambda: wf.set_task_status(db, tid, request.form.get("status", "")),
                      url_for("request_detail", rid=t["request_id"]))

    @app.post("/automation/run")
    def automation_run():
        n = wf.escalate_overdue(get_db())
        flash(f"Automation complete: {n} overdue request(s) escalated.", "ok")
        return redirect(url_for("dashboard"))

    @app.get("/api/metrics")
    def api_metrics():
        return jsonify(analytics.metrics(get_db()))

    @app.get("/reports/excel")
    def report_excel():
        name = f"biztrack_report_{date.today():%Y%m%d}.xlsx"
        return send_file(reports.report_bytes(get_db()), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.get("/export/<name>.csv")      # Power BI feeds: requests.csv, tasks.csv
    def export_csv(name):
        db = get_db()
        df = {"requests": analytics.requests_flat, "tasks": analytics.tasks_flat}.get(name) or abort(404)
        return Response(df(db).to_csv(index=False), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=biztrack_{name}.csv"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
