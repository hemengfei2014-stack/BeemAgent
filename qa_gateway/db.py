import csv
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Paths:
    root_dir: Path

    @property
    def enterprise_db_path(self) -> Path:
        return self.root_dir / "enterprise_data.db"

    @property
    def app_db_path(self) -> Path:
        return self.root_dir / "qa_gateway.db"

    @property
    def synthetic_data_dir(self) -> Path:
        return (
            self.root_dir
            / "fake_beem"
            / "simplified_schema"
            / "synthetic_data"
        )


def connect_sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_app_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY,
          org_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          title TEXT NOT NULL,
          created_at_ms INTEGER NOT NULL,
          updated_at_ms INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_owner_updated
          ON conversations(org_id, user_id, updated_at_ms DESC);

        CREATE TABLE IF NOT EXISTS conversation_messages (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          reasoning_content TEXT,
          created_at_ms INTEGER NOT NULL,
          FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conversation_time
          ON conversation_messages(conversation_id, created_at_ms ASC);

        CREATE TABLE IF NOT EXISTS tool_runs (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          org_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          trace_id TEXT NOT NULL,
          step_idx INTEGER NOT NULL,
          model TEXT NOT NULL,
          tool_call_id TEXT NOT NULL,
          tool_name TEXT NOT NULL,
          tool_args_json TEXT NOT NULL,
          ok INTEGER NOT NULL,
          error TEXT,
          result_refs_json TEXT NOT NULL,
          result_summary TEXT NOT NULL,
          tool_output_bytes INTEGER NOT NULL,
          truncated INTEGER NOT NULL,
          elapsed_ms INTEGER NOT NULL,
          created_at_ms INTEGER NOT NULL,
          FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_tool_runs_conversation_time
          ON tool_runs(conversation_id, created_at_ms ASC);
        CREATE INDEX IF NOT EXISTS idx_tool_runs_trace
          ON tool_runs(trace_id, step_idx ASC);
        """
    )
    conn.commit()


def _read_tsv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield {k: (v if v is not None else "") for k, v in row.items()}


def init_enterprise_db_if_needed(conn: sqlite3.Connection, synthetic_data_dir: Path) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS _meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        """
    )
    meta = conn.execute("SELECT value FROM _meta WHERE key='schema_version'").fetchone()
    if meta and meta["value"] == "2":
        return

    conn.executescript(
        """
        DROP TABLE IF EXISTS org;
        DROP TABLE IF EXISTS user;
        DROP TABLE IF EXISTS dept;
        DROP TABLE IF EXISTS dept_user;
        DROP TABLE IF EXISTS im_message;
        DROP TABLE IF EXISTS im_user_session;
        DROP TABLE IF EXISTS doc;
        DROP TABLE IF EXISTS doc_user_access;
        DROP TABLE IF EXISTS calendar_event;
        DROP TABLE IF EXISTS calendar_event_participant;
        DROP TABLE IF EXISTS doc_fts;

        CREATE TABLE org (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          short_name TEXT NOT NULL,
          owner_user_id TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE user (
          id TEXT NOT NULL,
          org_id TEXT NOT NULL,
          name TEXT NOT NULL,
          manager_id TEXT,
          role TEXT,
          mobile TEXT,
          email TEXT,
          join_date TEXT,
          gender TEXT,
          birthday TEXT,
          PRIMARY KEY (org_id, id)
        );

        CREATE INDEX idx_user_org_name ON user(org_id, name);

        CREATE TABLE dept (
          id TEXT NOT NULL,
          org_id TEXT NOT NULL,
          name TEXT NOT NULL,
          parent_id TEXT,
          leader_id TEXT,
          level TEXT,
          created_at TEXT,
          PRIMARY KEY (org_id, id)
        );

        CREATE INDEX idx_dept_org_name ON dept(org_id, name);

        CREATE TABLE dept_user (
          org_id TEXT NOT NULL,
          dept_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          created_at TEXT,
          PRIMARY KEY (org_id, dept_id, user_id)
        );

        CREATE INDEX idx_dept_user_by_user ON dept_user(org_id, user_id);
        CREATE INDEX idx_dept_user_by_dept ON dept_user(org_id, dept_id);

        CREATE TABLE im_message (
          org_id TEXT NOT NULL,
          session_id TEXT NOT NULL,
          conversation_type TEXT NOT NULL,
          message_id TEXT NOT NULL,
          from_user_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          send_time_ms INTEGER NOT NULL,
          message_type TEXT NOT NULL,
          content TEXT NOT NULL,
          PRIMARY KEY (org_id, message_id)
        );

        CREATE INDEX idx_im_message_session_time ON im_message(org_id, session_id, send_time_ms DESC);

        CREATE TABLE im_user_session (
          org_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          session_id TEXT NOT NULL,
          conversation_type TEXT NOT NULL,
          PRIMARY KEY (org_id, user_id, session_id)
        );

        CREATE INDEX idx_im_user_session_user ON im_user_session(org_id, user_id);

        CREATE TABLE doc (
          org_id TEXT NOT NULL,
          doc_id TEXT NOT NULL,
          create_time TEXT NOT NULL,
          update_time TEXT NOT NULL,
          ctype TEXT NOT NULL,
          title TEXT NOT NULL,
          note TEXT NOT NULL,
          content_length TEXT NOT NULL,
          owner TEXT NOT NULL,
          PRIMARY KEY (org_id, doc_id)
        );

        CREATE TABLE doc_user_access (
          org_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          doc_id TEXT NOT NULL,
          PRIMARY KEY (org_id, user_id, doc_id)
        );

        CREATE INDEX idx_doc_user_access_user ON doc_user_access(org_id, user_id);

        CREATE VIRTUAL TABLE doc_fts USING fts5(
          title,
          note,
          doc_id UNINDEXED,
          org_id UNINDEXED
        );

        CREATE TABLE calendar_event (
          event_id TEXT PRIMARY KEY,
          subject TEXT NOT NULL,
          start_time INTEGER NOT NULL,
          end_time INTEGER NOT NULL,
          organizer_id TEXT NOT NULL,
          participants TEXT NOT NULL
        );

        CREATE TABLE calendar_event_participant (
          event_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          PRIMARY KEY (event_id, user_id),
          FOREIGN KEY(event_id) REFERENCES calendar_event(event_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_calendar_participant_user ON calendar_event_participant(user_id);
        """
    )

    org_path = synthetic_data_dir / "org_system" / "data" / "org.txt"
    user_path = synthetic_data_dir / "org_system" / "data" / "user.txt"
    dept_path = synthetic_data_dir / "org_system" / "data" / "dept.txt"
    dept_user_path = synthetic_data_dir / "org_system" / "data" / "dept_user.txt"

    for row in _read_tsv_rows(org_path):
        conn.execute(
            "INSERT INTO org(id,name,short_name,owner_user_id,created_at) VALUES (?,?,?,?,?)",
            (row["id"], row["name"], row["short_name"], row["owner_user_id"], row["created_at"]),
        )

    for row in _read_tsv_rows(user_path):
        manager_id = row.get("manager_id", "").strip() or None
        conn.execute(
            """
            INSERT INTO user(
              id, org_id, name, manager_id, role, mobile, email, join_date, gender, birthday
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["id"],
                row["org_id"],
                row["name"],
                manager_id,
                row.get("role", ""),
                row.get("mobile", ""),
                row.get("email", ""),
                row.get("join_date", ""),
                row.get("gender", ""),
                row.get("birthday", ""),
            ),
        )

    if dept_path.exists():
        for row in _read_tsv_rows(dept_path):
            parent_id = row.get("parent_id", "").strip() or None
            leader_id = row.get("leader_id", "").strip() or None
            conn.execute(
                """
                INSERT INTO dept(
                  id, org_id, name, parent_id, leader_id, level, created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    row["id"],
                    row["org_id"],
                    row["name"],
                    parent_id,
                    leader_id,
                    row.get("level", ""),
                    row.get("created_at", ""),
                ),
            )

    if dept_user_path.exists():
        for row in _read_tsv_rows(dept_user_path):
            conn.execute(
                "INSERT INTO dept_user(org_id,dept_id,user_id,created_at) VALUES (?,?,?,?)",
                (row["org_id"], row["dept_id"], row["user_id"], row.get("created_at", "")),
            )

    msg_path = synthetic_data_dir / "message" / "data" / "ods_im_message_min.txt"
    part_path = synthetic_data_dir / "message" / "data" / "ods_im_session_participant_min.txt"
    for row in _read_tsv_rows(msg_path):
        conn.execute(
            """
            INSERT INTO im_message(
              org_id, session_id, conversation_type, message_id, from_user_id, target_id,
              send_time_ms, message_type, content
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                row["org_id"],
                row["session_id"],
                row["conversation_type"],
                row["message_id"],
                row["from_user_id"],
                row["target_id"],
                int(row["send_time_ms"]),
                row["message_type"],
                row["content"],
            ),
        )

    for row in _read_tsv_rows(part_path):
        org_id = row["org_id"]
        user_id = row["user_id"]
        session_ids = [s.strip() for s in row.get("session_ids", "").split(",") if s.strip()]
        types = [t.strip() for t in row.get("conversation_types", "").split(",") if t.strip()]
        for idx, session_id in enumerate(session_ids):
            conversation_type = types[idx] if idx < len(types) else ""
            conn.execute(
                "INSERT INTO im_user_session(org_id,user_id,session_id,conversation_type) VALUES (?,?,?,?)",
                (org_id, user_id, session_id, conversation_type),
            )

    doc_path = synthetic_data_dir / "doc" / "data" / "ods_docs_min.txt"
    access_path = synthetic_data_dir / "doc" / "data" / "dwd_user_doc_access_min.txt"
    for row in _read_tsv_rows(doc_path):
        conn.execute(
            """
            INSERT INTO doc(org_id,doc_id,create_time,update_time,ctype,title,note,content_length,owner)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                row["org_id"],
                row["doc_id"],
                row["create_time"],
                row.get("update_time", "") or row["create_time"],
                row["ctype"],
                row["title"],
                row["note"],
                row.get("content_length", "") or "",
                row["owner"],
            ),
        )
        conn.execute(
            "INSERT INTO doc_fts(title,note,doc_id,org_id) VALUES (?,?,?,?)",
            (row["title"], row["note"], row["doc_id"], row["org_id"]),
        )

    for row in _read_tsv_rows(access_path):
        org_id = row["user_org_id"]
        user_id = row["user_id"]
        doc_ids = [d.strip() for d in row.get("doc_ids", "").split(",") if d.strip()]
        for doc_id in doc_ids:
            conn.execute(
                "INSERT INTO doc_user_access(org_id,user_id,doc_id) VALUES (?,?,?)",
                (org_id, user_id, doc_id),
            )

    cal_path = synthetic_data_dir / "calendar" / "data" / "calendar_event.txt"
    for row in _read_tsv_rows(cal_path):
        conn.execute(
            """
            INSERT INTO calendar_event(event_id,subject,start_time,end_time,organizer_id,participants)
            VALUES (?,?,?,?,?,?)
            """,
            (
                row["event_id"],
                row["subject"],
                int(row["start_time"]),
                int(row["end_time"]),
                row["organizer_id"],
                row["participants"],
            ),
        )
        participants = [p.strip() for p in row.get("participants", "").split(",") if p.strip()]
        for p in participants:
            conn.execute(
                "INSERT INTO calendar_event_participant(event_id,user_id) VALUES (?,?)",
                (row["event_id"], p),
            )

    conn.execute("DELETE FROM _meta WHERE key='schema_version'")
    conn.execute("INSERT INTO _meta(key,value) VALUES ('schema_version','2')")
    conn.commit()
