use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Value};

use crate::db;
use crate::source::resolve_source;

const MAX_FIRST_LINE: usize = 256 * 1024;
const MAX_TAIL: usize = 64 * 1024;

pub fn sessions_dir() -> PathBuf {
    if let Ok(env_dir) = std::env::var("CODEX_SESSIONS_DIR") {
        let trimmed = env_dir.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    if let Ok(home) = std::env::var("CODEX_HOME") {
        return PathBuf::from(home).join("sessions");
    }
    dirs_fallback().join(".codex").join("sessions")
}

fn dirs_fallback() -> PathBuf {
    std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

pub fn list_session_catalog(current_source: Option<&Path>, root: Option<&Path>) -> Value {
    let root = root.map(Path::to_path_buf).unwrap_or_else(sessions_dir);
    let titles = load_titles(&root);
    let mut groups: BTreeMap<String, Value> = BTreeMap::new();
    let mut scanned = 0u64;
    let mut skipped = 0u64;
    if let Ok(walker) = fs::read_dir(&root) {
        walk(&root, walker, &mut scanned, &mut skipped, &titles, &mut groups);
    }
    let mut projects: Vec<Value> = groups.into_values().collect();
    for project in &mut projects {
        let first_title = if let Some(sessions) = project.get_mut("sessions").and_then(Value::as_array_mut) {
            sessions.sort_by(|a, b| {
                b.get("timestamp")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .cmp(a.get("timestamp").and_then(Value::as_str).unwrap_or(""))
            });
            sessions.first().and_then(|row| row.get("title")).cloned()
        } else {
            None
        };
        if project.get("latest_title").and_then(Value::as_str).unwrap_or("").is_empty() {
            if let Some(title) = first_title {
                project["latest_title"] = title;
            }
        }
    }
    projects.sort_by(|a, b| {
        let a_ready = if a.get("has_harness").and_then(Value::as_bool).unwrap_or(false) { 0 } else { 1 };
        let b_ready = if b.get("has_harness").and_then(Value::as_bool).unwrap_or(false) { 0 } else { 1 };
        b.get("latest")
            .and_then(Value::as_str)
            .unwrap_or("")
            .cmp(a.get("latest").and_then(Value::as_str).unwrap_or(""))
            .then(a_ready.cmp(&b_ready))
    });
    let suggested = suggest(&projects, current_source);
    json!({
        "sessions_dir": root.to_string_lossy(),
        "source": current_source.map(|p| p.to_string_lossy().into_owned()),
        "scanned": scanned,
        "skipped": skipped,
        "suggested": suggested,
        "projects": projects
    })
}

fn walk(
    root: &Path,
    reader: fs::ReadDir,
    scanned: &mut u64,
    skipped: &mut u64,
    titles: &BTreeMap<String, String>,
    groups: &mut BTreeMap<String, Value>,
) {
    for entry in reader.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().into_owned();
        if path.is_dir() {
            if name == "__backups__" || name.starts_with("__backup_") {
                continue;
            }
            if let Ok(child) = fs::read_dir(&path) {
                walk(root, child, scanned, skipped, titles, groups);
            }
            continue;
        }
        if !name.ends_with(".jsonl") {
            continue;
        }
        *scanned += 1;
        let Some(meta) = parse_session_meta(&path) else {
            *skipped += 1;
            continue;
        };
        let cwd = meta.get("cwd").and_then(Value::as_str).unwrap_or("").to_string();
        let sid = meta.get("id").and_then(Value::as_str).unwrap_or("").to_string();
        let timestamp = meta.get("timestamp").and_then(Value::as_str).unwrap_or("").to_string();
        let mtime = iso_mtime(&path);
        let latest = if timestamp > mtime { timestamp.clone() } else { mtime.clone() };
        let title = titles
            .get(&sid)
            .cloned()
            .unwrap_or_else(|| {
                Path::new(&cwd)
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or(if sid.is_empty() { path.file_stem().and_then(|n| n.to_str()).unwrap_or("") } else { &sid })
                    .to_string()
            });
        let rel = path.strip_prefix(root).map(|p| p.to_string_lossy().into_owned()).unwrap_or_else(|_| path.to_string_lossy().into_owned());
        let key = if cwd.is_empty() {
            format!("session:{}", if sid.is_empty() { name } else { sid.clone() })
        } else {
            cwd_key(&cwd)
        };
        let group = groups.entry(key).or_insert_with(|| {
            let probe = if cwd.is_empty() {
                json!({
                    "cwd": "",
                    "cwd_exists": false,
                    "has_harness": false,
                    "source": Value::Null,
                    "tasks_file": Value::Null,
                    "project_name": Value::Null,
                    "task_count": Value::Null
                })
            } else {
                probe_harness(&cwd)
            };
            let mut group = probe;
            group["cwd"] = json!(cwd);
            group["latest"] = json!(latest);
            group["session_count"] = json!(0);
            group["sessions"] = json!([]);
            group
        });
        if let Some(sessions) = group.get_mut("sessions").and_then(Value::as_array_mut) {
            sessions.push(json!({
                "id": sid,
                "title": title,
                "timestamp": if timestamp.is_empty() { mtime.clone() } else { timestamp },
                "mtime": mtime,
                "cwd": cwd,
                "file": rel
            }));
        }
        let count = group.get("session_count").and_then(Value::as_u64).unwrap_or(0) + 1;
        group["session_count"] = json!(count);
        if latest.as_str() > group.get("latest").and_then(Value::as_str).unwrap_or("") {
            group["latest"] = json!(latest);
            if !title.is_empty() {
                group["latest_title"] = json!(title);
            }
        } else if group.get("latest_title").and_then(Value::as_str).unwrap_or("").is_empty() && !title.is_empty() {
            group["latest_title"] = json!(title);
        }
        if group.get("project_name").and_then(Value::as_str).unwrap_or("").is_empty() {
            group["project_name"] = json!(Path::new(&cwd).file_name().and_then(|n| n.to_str()));
        }
    }
}

pub fn probe_harness(cwd: &str) -> Value {
    let mut info = json!({
        "cwd": cwd,
        "cwd_exists": false,
        "has_harness": false,
        "source": Value::Null,
        "tasks_file": Value::Null,
        "project_name": Value::Null,
        "task_count": Value::Null
    });
    if cwd.is_empty() {
        return info;
    }
    let target = PathBuf::from(cwd);
    info["cwd_exists"] = json!(target.exists());
    if !target.exists() {
        let nested = if target.file_name().and_then(|n| n.to_str()) == Some(".harness") {
            target
        } else {
            target.join(".harness")
        };
        info["source"] = json!(nested.to_string_lossy());
        return info;
    }
    let Ok(source) = resolve_source(&target, true) else {
        return info;
    };
    info["source"] = json!(source.to_string_lossy());
    let db = source.join("harness.db");
    if db.is_file() {
        info["has_harness"] = json!(true);
        info["tasks_file"] = json!(db.to_string_lossy());
        let (name, count) = db_task_meta(&db);
        info["project_name"] = json!(name);
        info["task_count"] = json!(count);
    }
    info
}

fn db_task_meta(db_file: &Path) -> (Option<String>, Option<i64>) {
    let uri = db::sqlite_uri(db_file);
    let Ok(conn) = Connection::open_with_flags(&uri, OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_URI) else {
        return (None, None);
    };
    let name = conn
        .query_row("SELECT value_json FROM meta WHERE key = 'project'", [], |row| row.get::<_, String>(0))
        .ok()
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .and_then(|value| match value {
            Value::String(text) if !text.is_empty() => Some(text),
            _ => None,
        });
    let count = conn.query_row("SELECT COUNT(*) FROM tasks", [], |row| row.get::<_, i64>(0)).ok();
    (name, count)
}

fn load_titles(root: &Path) -> BTreeMap<String, String> {
    let mut titles = BTreeMap::new();
    let index = root.parent().unwrap_or(root).join("session_index.jsonl");
    let Ok(raw) = fs::read_to_string(index) else {
        return titles;
    };
    for line in raw.lines() {
        let Ok(Value::Object(row)) = serde_json::from_str::<Value>(line) else { continue; };
        let sid = row.get("id").and_then(Value::as_str).unwrap_or("").trim().to_string();
        let name = row
            .get("thread_name")
            .or_else(|| row.get("title"))
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string();
        if !sid.is_empty() && !name.is_empty() {
            titles.insert(sid, name);
        }
    }
    titles
}

fn parse_session_meta(path: &Path) -> Option<Value> {
    let line = first_line(path)?;
    let record: Value = serde_json::from_str(&line).ok()?;
    let obj = record.as_object()?;
    let payload = obj.get("payload").and_then(Value::as_object);
    let mut meta = if obj.get("type").and_then(Value::as_str) == Some("session_meta") {
        payload.cloned().map(Value::Object)
    } else if payload.and_then(|p| p.get("cwd")).is_some() {
        payload.cloned().map(Value::Object)
    } else if obj.get("cwd").is_some() && (obj.get("id").is_some() || obj.get("session_id").is_some()) && obj.get("type").is_none() {
        Some(record.clone())
    } else {
        None
    }?;
    if meta.get("id").and_then(Value::as_str).unwrap_or("").is_empty() {
        if let Some(sid) = meta.get("session_id").cloned() {
            meta["id"] = sid;
        }
    }
    if meta.get("timestamp").and_then(Value::as_str).unwrap_or("").is_empty() {
        meta["timestamp"] = obj.get("timestamp").cloned().unwrap_or(json!(""));
    }
    if meta.get("cwd").and_then(Value::as_str).unwrap_or("").is_empty() {
        meta["cwd"] = json!(extract_tail_cwd(path));
    }
    Some(meta)
}

fn first_line(path: &Path) -> Option<String> {
    let data = fs::read(path).ok()?;
    let slice = if data.len() > MAX_FIRST_LINE { &data[..MAX_FIRST_LINE] } else { &data };
    let line = slice.split(|b| *b == b'\n').next().unwrap_or(slice);
    Some(String::from_utf8_lossy(line).trim().trim_start_matches('\u{feff}').to_string()).filter(|s| !s.is_empty())
}

fn extract_tail_cwd(path: &Path) -> String {
    let Ok(data) = fs::read(path) else { return String::new(); };
    let start = data.len().saturating_sub(MAX_TAIL);
    let text = String::from_utf8_lossy(&data[start..]);
    let mut lines: Vec<&str> = text.lines().collect();
    if start > 0 && !lines.is_empty() {
        lines.remove(0);
    }
    for line in lines.into_iter().rev() {
        let line = line.trim();
        if line.is_empty() { continue; }
        let Ok(record) = serde_json::from_str::<Value>(line) else { continue; };
        let payload = record.get("payload").unwrap_or(&record);
        let cwd = payload.get("cwd").and_then(Value::as_str).unwrap_or("").trim();
        let ty = record.get("type").and_then(Value::as_str);
        if !cwd.is_empty() && matches!(ty, Some("turn_context" | "session_meta" | "event_msg") | None) {
            return cwd.to_string();
        }
    }
    String::new()
}

fn cwd_key(cwd: &str) -> String {
    cwd.trim().trim_end_matches(['\\', '/']).replace('/', "\\").to_lowercase()
}

fn iso_mtime(path: &Path) -> String {
    let Ok(meta) = fs::metadata(path) else { return String::new(); };
    let Ok(modified) = meta.modified() else { return String::new(); };
    let secs = modified.duration_since(UNIX_EPOCH).unwrap_or_default().as_secs() as i64;
    unix_to_iso(secs)
}

fn unix_to_iso(secs: i64) -> String {
    let days = secs.div_euclid(86400);
    let rem = secs.rem_euclid(86400);
    let hour = rem / 3600;
    let min = (rem % 3600) / 60;
    let sec = rem % 60;
    let (year, month, day) = civil_from_days(days);
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{min:02}:{sec:02}Z")
}

fn civil_from_days(z: i64) -> (i32, u32, u32) {
    let z = z + 719468;
    let era = z.div_euclid(146097);
    let doe = z.rem_euclid(146097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = mp + if mp < 10 { 3 } else { -9 };
    let y = y + if m <= 2 { 1 } else { 0 };
    (y as i32, m as u32, d as u32)
}

fn suggest(projects: &[Value], _current: Option<&Path>) -> Value {
    let ready: Vec<&Value> = projects
        .iter()
        .filter(|row| row.get("has_harness").and_then(Value::as_bool).unwrap_or(false) && row.get("cwd_exists").and_then(Value::as_bool).unwrap_or(false))
        .collect();
    if ready.is_empty() {
        return Value::Null;
    }
    let newest = projects.iter().max_by_key(|row| row.get("latest").and_then(Value::as_str).unwrap_or(""));
    if let Some(newest) = newest {
        if newest.get("has_harness").and_then(Value::as_bool).unwrap_or(false) && newest.get("cwd_exists").and_then(Value::as_bool).unwrap_or(false) {
            return json!({
                "cwd": newest.get("cwd"),
                "source": newest.get("source"),
                "title": newest.get("latest_title").or_else(|| newest.get("project_name")),
                "reason": "latest_session"
            });
        }
    }
    if ready.len() == 1 {
        let row = ready[0];
        return json!({
            "cwd": row.get("cwd"),
            "source": row.get("source"),
            "title": row.get("latest_title").or_else(|| row.get("project_name")),
            "reason": "single_harness"
        });
    }
    Value::Null
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn probe_reads_meta_project_not_task_column() {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let root = std::env::temp_dir().join(format!("taskboard-sess-{unique}"));
        let harness = root.join(".harness");
        fs::create_dir_all(&harness).unwrap();
        let db = harness.join("harness.db");
        let conn = Connection::open(&db).unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO meta VALUES ('schema_version','1');
            INSERT INTO meta VALUES ('project', '"数据库项目"');
            INSERT INTO tasks(id, payload_json) VALUES ('t-1', '{"id":"t-1"}');
            "#,
        ).unwrap();
        drop(conn);
        let info = probe_harness(root.to_str().unwrap());
        assert_eq!(info["has_harness"], true);
        assert_eq!(info["project_name"], "数据库项目");
        assert_eq!(info["task_count"], 1);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn unix_to_iso_formats_epoch() {
        assert_eq!(unix_to_iso(0), "1970-01-01T00:00:00Z");
        assert_eq!(unix_to_iso(1_694_563_200), "2023-09-13T00:00:00Z");
    }
}
