import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from datetime import date, timedelta
from app import create_app
from db import connect
import workflow as wf


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True})


@pytest.fixture
def db(app):
    c = connect(app.config["DATABASE"]); yield c; c.close()


def mk(client, **kw):
    data = dict(title="Fix VPN", requester="A", department="IT", category="IT Support", priority="Low",
                due_date=(date.today() + timedelta(days=5)).isoformat()); data.update(kw)
    return client.post("/requests/new", data=data)


def test_create_and_validation(app):
    c = app.test_client()
    assert mk(c).status_code == 302
    assert mk(c, title="").status_code == 400
    assert mk(c, priority="Nope").status_code == 400


def test_invalid_transition(app, db):
    mk(app.test_client())
    with pytest.raises(wf.WorkflowError):
        wf.set_request_status(db, 1, "Completed")


def test_task_automation_cycle(app, db):
    mk(app.test_client())
    t1, t2 = wf.add_task(db, 1, "a", "X"), wf.add_task(db, 1, "b", "Y")
    wf.set_task_status(db, t1, "In Progress")
    assert db.execute("SELECT status FROM requests WHERE id=1").fetchone()[0] == "In Progress"
    wf.set_task_status(db, t1, "Done"); wf.set_task_status(db, t2, "Done")
    assert db.execute("SELECT status FROM requests WHERE id=1").fetchone()[0] == "Completed"
    wf.add_task(db, 1, "c", "Z")
    assert db.execute("SELECT status FROM requests WHERE id=1").fetchone()[0] == "In Progress"


def test_escalation(app, db):
    mk(app.test_client(), due_date=(date.today() - timedelta(days=10)).isoformat())
    assert wf.escalate_overdue(db) == 1
    assert db.execute("SELECT priority FROM requests WHERE id=1").fetchone()[0] == "Critical"


def test_endpoints_and_excel(app):
    c = app.test_client(); mk(c)
    assert c.get("/").status_code == 200
    assert c.get("/requests?status=New").status_code == 200
    assert c.get("/api/metrics").json["kpis"]["total"] == 1
    assert c.get("/export/requests.csv").status_code == 200
    r = c.get("/reports/excel")
    assert r.status_code == 200 and r.data[:2] == b"PK"


def test_kanban_and_api(app, db):
    c = app.test_client()
    mk(c)

    # Test Kanban HTML page
    res = c.get("/kanban")
    assert res.status_code == 200
    assert b"Kanban Board" in res.data
    assert b"#1" in res.data

    # Test valid transition via AJAX/API: New -> In Progress
    api_res = c.post("/api/requests/1/status", json={"status": "In Progress"})
    assert api_res.status_code == 200
    assert api_res.json["ok"] is True
    assert api_res.json["status"] == "In Progress"
    assert db.execute("SELECT status FROM requests WHERE id=1").fetchone()[0] == "In Progress"

    # Test invalid transition via AJAX/API: In Progress cannot jump directly to New
    bad_res = c.post("/api/requests/1/status", json={"status": "New"})
    assert bad_res.status_code == 400
    assert bad_res.json["ok"] is False
    assert "Cannot move request" in bad_res.json["error"]
