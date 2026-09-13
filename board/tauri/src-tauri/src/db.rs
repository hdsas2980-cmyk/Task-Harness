use std::path::Path;

use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

pub const SCHEMA_VERSION: i64 = 1;

pub fn empty_snapshot(path: Option<&Path>) -> Value {
    json!({
        "schema_version": SCHEMA_VERSION,
        "storage": {"type": "sqlite", "path": path.map(|p| p.to_string_lossy().into_owned())},
        "meta": {"schema_version": SCHEMA_VERSION},
        "tasks": [],
        "evidence": [],
        "reviews": [],
        "progress": "",
        "board": {},
        "project": Value::Null,
        "counts": {"tasks": 0, "evidence": 0, "reviews": 0},
        "revision": {
            "schema_version": SCHEMA_VERSION,
            "counts": {"tasks": 0, "evidence": 0, "reviews": 0},
            "meta_rev": Value::Null,
            "progress_hash": ""
        }
    })
}

pub fn read_snapshot(path: &Path) -> Result<Value, String> {
    if !path.is_file() {
        return Err(format!("harness.db：数据库不存在: {}", path.display()));
    }
    let uri = sqlite_uri(path);
    let conn = Connection::open_with_flags(
        &uri,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_URI,
    )
    .map_err(|err| format!("harness.db：无法读取 SQLite 数据库（{err}）"))?;
    let _ = conn.execute_batch("PRAGMA foreign_keys = ON;");
    let schema_version = schema_version(&conn)?;
    if schema_version != SCHEMA_VERSION {
        return Err(format!(
            "不支持的 harness.db schema_version={schema_version}，当前桌面入口只读 v{SCHEMA_VERSION}"
        ));
    }
    let (tasks, task_latest) = unpack_table(&conn, "SELECT id, payload_json, created_at FROM tasks ORDER BY rowid")?;
    let (evidence, evidence_latest) =
        unpack_table(&conn, "SELECT id, payload_json, created_at FROM evidence ORDER BY rowid")?;
    let (reviews, review_latest) =
        unpack_table(&conn, "SELECT id, payload_json, created_at FROM reviews ORDER BY rowid")?;
    let mut progress_parts = Vec::new();
    let mut progress_latest = String::new();
    let mut progress_stmt = conn
        .prepare("SELECT content, created_at FROM progress ORDER BY id")
        .map_err(db_err)?;
    let progress_rows = progress_stmt
        .query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)))
        .map_err(db_err)?;
    for row in progress_rows {
        let (content, created) = row.map_err(db_err)?;
        progress_parts.push(content);
        if created > progress_latest {
            progress_latest = created;
        }
    }
    let progress = progress_parts.join("\n\n");
    let progress_count = progress_parts.len();
    let meta = read_meta(&conn)?;
    let mut latest = task_latest;
    for candidate in [evidence_latest, review_latest, progress_latest] {
        if candidate > latest {
            latest = candidate;
        }
    }
    let board = meta
        .get("board")
        .cloned()
        .filter(|value| value.is_object())
        .unwrap_or_else(|| json!({}));
    let project = meta.get("project").cloned().unwrap_or(Value::Null);
    let meta_rev = meta.get("rev").cloned().unwrap_or(Value::Null);
    let task_count = tasks.len();
    let evidence_count = evidence.len();
    let review_count = reviews.len();
    let progress_hash = if progress.is_empty() {
        String::new()
    } else {
        sha256_hex(&progress)
    };
    let _ = (progress_count, latest);
    Ok(json!({
        "schema_version": schema_version,
        "storage": {"type": "sqlite", "path": path.to_string_lossy()},
        "meta": meta,
        "tasks": tasks,
        "evidence": evidence,
        "reviews": reviews,
        "progress": progress,
        "board": board,
        "project": project,
        "counts": {
            "tasks": task_count,
            "evidence": evidence_count,
            "reviews": review_count
        },
        "revision": {
            "schema_version": schema_version,
            "counts": {
                "tasks": task_count,
                "evidence": evidence_count,
                "reviews": review_count
            },
            "meta_rev": meta_rev,
            "progress_hash": progress_hash,
        }
    }))
}

pub fn sqlite_uri(path: &Path) -> String {
    let posix = path.to_string_lossy().replace('\\', "/");
    let mut encoded = String::new();
    for ch in posix.chars() {
        match ch {
            ' ' => encoded.push_str("%20"),
            '#' => encoded.push_str("%23"),
            '?' => encoded.push_str("%3F"),
            '%' => encoded.push_str("%25"),
            _ => encoded.push(ch),
        }
    }
    let trimmed = encoded.trim_start_matches('/');
    format!("file:///{trimmed}?mode=ro")
}

fn schema_version(conn: &Connection) -> Result<i64, String> {
    let raw: Result<String, _> =
        conn.query_row("SELECT value_json FROM meta WHERE key = 'schema_version'", [], |row| row.get(0));
    match raw {
        Ok(text) => serde_json::from_str::<Value>(&text)
            .ok()
            .and_then(|value| value.as_i64().or_else(|| value.as_u64().map(|n| n as i64)))
            .ok_or_else(|| "不支持的 harness.db schema_version=?, 当前桌面入口只读 v1".into()),
        Err(_) => Ok(0),
    }
}

fn read_meta(conn: &Connection) -> Result<Map<String, Value>, String> {
    let mut stmt = conn
        .prepare("SELECT key, value_json FROM meta")
        .map_err(db_err)?;
    let rows = stmt
        .query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)))
        .map_err(db_err)?;
    let mut meta = Map::new();
    for row in rows {
        let (key, raw) = row.map_err(db_err)?;
        let value = serde_json::from_str(&raw).unwrap_or(Value::String(raw));
        meta.insert(key, value);
    }
    Ok(meta)
}

fn unpack_table(conn: &Connection, sql: &str) -> Result<(Vec<Value>, String), String> {
    let mut stmt = conn.prepare(sql).map_err(db_err)?;
    let rows = stmt
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        })
        .map_err(db_err)?;
    let mut items = Vec::new();
    let mut latest = String::new();
    for row in rows {
        let (id, payload_json, created_at) = row.map_err(db_err)?;
        let payload: Value = serde_json::from_str(&payload_json)
            .map_err(|err| format!("harness.db：payload_json 无法解析（{err}）"))?;
        if !payload.is_object() {
            return Err(format!("harness.db：payload_json 必须是对象（id={id}）"));
        }
        let mut item = payload.clone();
        if item.get("id").and_then(Value::as_str).unwrap_or("").is_empty() {
            item["id"] = Value::String(id.clone());
        }
        item["payload"] = payload;
        items.push(item);
        if created_at > latest {
            latest = created_at;
        }
    }
    Ok((items, latest))
}

fn db_err(err: rusqlite::Error) -> String {
    format!("harness.db：无法读取 SQLite 数据库（{err}）")
}

fn sha256_hex(text: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(text.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn missing_file_does_not_create_database() {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let path = std::env::temp_dir().join(format!("missing-{unique}.db"));
        let err = read_snapshot(&path).unwrap_err();
        assert!(err.contains("不存在") || err.contains("无法读取"));
        assert!(!path.exists());
    }

    #[test]
    fn unpacks_payload_and_joins_progress() {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("taskboard-db-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("harness.db");
        {
            let conn = Connection::open(&path).unwrap();
            conn.execute_batch(
                r#"
                CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
                CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE evidence (id TEXT PRIMARY KEY, task_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE reviews (id TEXT PRIMARY KEY, task_id TEXT, evidence_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE progress (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO meta VALUES ('schema_version', '1');
                INSERT INTO meta VALUES ('project', '"测试项目"');
                INSERT INTO tasks(id, payload_json) VALUES ('t-000', '{"id":"t-000","name":"任务","unknown_task_field":{"nested":0}}');
                INSERT INTO progress(content, content_hash) VALUES ('第一段', 'a');
                INSERT INTO progress(content, content_hash) VALUES ('第二段', 'b');
                "#,
            )
            .unwrap();
        }
        let before = fs::read(&path).unwrap();
        let snap = read_snapshot(&path).unwrap();
        assert_eq!(snap["meta"]["project"], "测试项目");
        assert_eq!(snap["tasks"][0]["id"], "t-000");
        assert_eq!(snap["tasks"][0]["payload"]["unknown_task_field"]["nested"], 0);
        assert_eq!(snap["progress"], "第一段\n\n第二段");
        assert_eq!(fs::read(&path).unwrap(), before);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn sqlite_uri_is_readonly_and_absolute() {
        let uri = sqlite_uri(Path::new(r"E:\\demo\\harness.db"));
        assert!(uri.starts_with("file:///"));
        assert!(uri.contains("mode=ro"));
        assert!(!uri.contains("immutable"));
        assert!(!uri.contains("mode=rw"));
    }

    fn make_db(sql: &str) -> (std::path::PathBuf, std::path::PathBuf) {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("taskboard-db-extra-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("harness.db");
        let conn = Connection::open(&path).unwrap();
        conn.execute_batch(sql).unwrap();
        drop(conn);
        (dir, path)
    }

    #[test]
    fn schema_v2_is_rejected() {
        let (dir, path) = make_db(
            r#"
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO meta VALUES ('schema_version', '2');
            "#,
        );
        let err = read_snapshot(&path).unwrap_err();
        assert!(err.contains("schema_version=2"), "{err}");
        assert!(path.is_file());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn missing_tasks_table_fails_closed() {
        let (dir, path) = make_db(
            r#"
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            INSERT INTO meta VALUES ('schema_version', '1');
            "#,
        );
        let before = fs::read(&path).unwrap();
        let err = read_snapshot(&path).unwrap_err();
        assert!(err.contains("无法读取") || err.contains("no such table"), "{err}");
        assert_eq!(fs::read(&path).unwrap(), before);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn non_object_payload_fails_closed() {
        let (dir, path) = make_db(
            r#"
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE evidence (id TEXT PRIMARY KEY, task_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE reviews (id TEXT PRIMARY KEY, task_id TEXT, evidence_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE progress (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO meta VALUES ('schema_version', '1');
            INSERT INTO tasks(id, payload_json) VALUES ('t-1', '[]');
            "#,
        );
        let err = read_snapshot(&path).unwrap_err();
        assert!(err.contains("payload_json 必须是对象"), "{err}");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn sqlite_uri_encodes_space() {
        let uri = sqlite_uri(Path::new(r"E:\my dir\harness.db"));
        assert!(uri.contains("%20"));
        assert!(uri.ends_with("?mode=ro"));
        assert!(!uri.contains("immutable"));
    }
}
