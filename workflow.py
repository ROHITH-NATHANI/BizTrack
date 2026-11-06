"""Workflow engine: status transitions + automated status updates."""
from datetime import date
from db import now

REQUEST_STATUSES = ["New", "In Progress", "On Hold", "Completed", "Cancelled"]
TASK_STATUSES = ["To Do", "In Progress", "Done"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
CATEGORIES = ["IT Support", "Finance", "HR", "Procurement", "Facilities", "Operations"]
OPEN = ("New", "In Progress", "On Hold")

TRANSITIONS = {
    "New": ["In Progress", "Cancelled"],
    "In Progress": ["On Hold", "Completed", "Cancelled"],
    "On Hold": ["In Progress", "Cancelled"],
    "Completed": ["In Progress"],          # reopen
    "Cancelled": [],
}


class WorkflowError(ValueError):
    pass


def log(db, entity, entity_id, old, new, note=""):
    db.execute(
        "INSERT INTO status_log(entity, entity_id, old_status, new_status, note, changed_at) "
        "VALUES (?,?,?,?,?,?)", (entity, entity_id, old, new, note, now()))


def set_request_status(db, rid, new, note="", force=False):
    row = db.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()
    if row is None:
        raise WorkflowError("Request not found")
    old = row["status"]
    if new not in REQUEST_STATUSES:
        raise WorkflowError(f"Invalid status '{new}'")
    if old == new:
        return old
    if not force and new not in TRANSITIONS[old]:
        raise WorkflowError(f"Cannot move request from '{old}' to '{new}'")
    closed = now() if new in ("Completed", "Cancelled") else None
    db.execute("UPDATE requests SET status=?, closed_at=?, updated_at=? WHERE id=?",
               (new, closed, now(), rid))
    log(db, "request", rid, old, new, note)
    db.commit()
    return new


def add_task(db, rid, title, assignee, due_date=None):
    req = db.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()
    if req is None:
        raise WorkflowError("Request not found")
    if req["status"] == "Cancelled":
        raise WorkflowError("Cannot add tasks to a cancelled request")
    cur = db.execute(
        "INSERT INTO tasks(request_id, title, assignee, due_date, created_at) VALUES (?,?,?,?,?)",
        (rid, title, assignee, due_date or None, now()))
    log(db, "task", cur.lastrowid, None, "To Do", "created")
    if req["status"] == "Completed":     # automation: new work reopens request
        set_request_status(db, rid, "In Progress", "auto: task added to completed request")
    db.commit()
    return cur.lastrowid


def set_task_status(db, tid, new):
    t = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if t is None or new not in TASK_STATUSES:
        raise WorkflowError("Invalid task or status")
    if t["status"] == new:
        return
    db.execute("UPDATE tasks SET status=?, completed_at=? WHERE id=?",
               (new, now() if new == "Done" else None, tid))
    log(db, "task", tid, t["status"], new)
    db.commit()
    sync_request_from_tasks(db, t["request_id"])


def sync_request_from_tasks(db, rid):
    """Automation: derive request status from its tasks."""
    req = db.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()
    statuses = [r["status"] for r in db.execute("SELECT status FROM tasks WHERE request_id=?", (rid,))]
    if not statuses or req["status"] == "Cancelled":
        return
    if req["status"] in ("New", "On Hold") and any(s in ("In Progress", "Done") for s in statuses):
        set_request_status(db, rid, "In Progress", "auto: work started on a task")
        req = {"status": "In Progress"}
    if all(s == "Done" for s in statuses) and req["status"] == "In Progress":
        set_request_status(db, rid, "Completed", "auto: all tasks done")
    elif req["status"] == "Completed" and not all(s == "Done" for s in statuses):
        set_request_status(db, rid, "In Progress", "auto: task reopened")


def escalate_overdue(db):
    """Automation: bump priority of overdue open requests. Returns #escalated."""
    today = date.today().isoformat()
    rows = db.execute(
        f"SELECT id, priority, CAST(julianday(?) - julianday(due_date) AS INT) AS days "
        f"FROM requests WHERE status IN ({','.join('?' * len(OPEN))}) AND due_date < ?",
        (today, *OPEN, today)).fetchall()
    n = 0
    for r in rows:
        new = None
        if r["days"] >= 7 and r["priority"] in ("Low", "Medium", "High"):
            new = "Critical"
        elif r["days"] >= 1 and r["priority"] in ("Low", "Medium"):
            new = "High"
        if new:
            db.execute("UPDATE requests SET priority=?, updated_at=? WHERE id=?", (new, now(), r["id"]))
            log(db, "request", r["id"], r["priority"], new, f"auto-escalated: {r['days']}d overdue")
            n += 1
    db.commit()
    return n
