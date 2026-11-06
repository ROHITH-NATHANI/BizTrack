DROP TABLE IF EXISTS status_log;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS requests;

CREATE TABLE requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    category    TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT 'Medium',
    status      TEXT NOT NULL DEFAULT 'New',
    requester   TEXT NOT NULL,
    department  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT
);

CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id   INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    assignee     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'To Do',
    due_date     TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE status_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity     TEXT NOT NULL,            -- 'request' | 'task'
    entity_id  INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    note       TEXT DEFAULT '',
    changed_at TEXT NOT NULL
);

CREATE INDEX idx_requests_status ON requests(status);
CREATE INDEX idx_requests_due    ON requests(due_date);
CREATE INDEX idx_tasks_request   ON tasks(request_id);
