use std::path::{Path, PathBuf};

use serde_json::{json, Value};

use crate::{contract, db};

pub fn resolve_source(project: &Path, must_exist: bool) -> Result<PathBuf, String> {
    let expanded = expand_user(project);
    let target = normalize(&expanded);
    if must_exist && !target.exists() {
        return Err(format!("项目目录不存在: {}", target.display()));
    }
    let target = if target.is_file() {
        target.parent().unwrap_or(&target).to_path_buf()
    } else {
        target
    };
    if target
        .file_name()
        .and_then(|name| name.to_str())
        .map(|name| name.eq_ignore_ascii_case(".harness"))
        .unwrap_or(false)
    {
        return Ok(target);
    }
    let nested = target.join(".harness");
    if nested.join("harness.db").is_file() {
        return Ok(nested);
    }
    if target.join("harness.db").is_file() {
        return Ok(target);
    }
    Ok(nested)
}

pub fn bind_source(raw: &str) -> Result<PathBuf, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("请提供项目根或 .harness 目录".into());
    }
    let path = PathBuf::from(trimmed);
    if path
        .components()
        .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        // still allow after normalize if the resolved directory exists
    }
    resolve_source(&path, true)
}

pub fn snapshot(source: Option<&Path>, last_source: Option<String>) -> Value {
    match source {
        None => json!({
            "source": Value::Null,
            "files": {},
            "snapshot": Value::Null,
            "contract": Value::Null,
            "last_source": last_source,
        }),
        Some(dir) => {
            let db_path = dir.join("harness.db");
            if db_path.is_file() {
                match db::read_snapshot(&db_path) {
                    Ok(snap) => {
                        let i18n = dir.join("board.i18n.json").is_file();
                        let contract = contract::validate_snapshot(&snap, true, i18n, None);
                        json!({
                            "source": dir.to_string_lossy(),
                            "files": {},
                            "snapshot": snap,
                            "contract": contract,
                            "last_source": last_source,
                        })
                    }
                    Err(err) => json!({
                        "source": dir.to_string_lossy(),
                        "files": {},
                        "snapshot": db::empty_snapshot(Some(&db_path)),
                        "contract": {"errors": [err], "counts": {}},
                        "last_source": last_source,
                    }),
                }
            } else {
                let err = format!("未初始化 {}，禁止回退 JSON/JSONL/TXT", db_path.display());
                json!({
                    "source": dir.to_string_lossy(),
                    "files": {},
                    "snapshot": Value::Null,
                    "contract": {"errors": [err], "counts": {"tasks": 0, "evidence": 0, "reviews": 0}},
                    "last_source": last_source,
                })
            }
        }
    }
}

fn expand_user(path: &Path) -> PathBuf {
    let raw = path.to_string_lossy();
    if let Some(rest) = raw.strip_prefix("~/") {
        if let Ok(home) = std::env::var("USERPROFILE") {
            return PathBuf::from(home).join(rest);
        }
    }
    path.to_path_buf()
}

fn normalize(path: &Path) -> PathBuf {
    if path.exists() {
        dunce_canonicalize(path).unwrap_or_else(|| path.to_path_buf())
    } else {
        PathBuf::from(path.to_string_lossy().replace('/', "\\"))
    }
}

fn dunce_canonicalize(path: &Path) -> Option<PathBuf> {
    std::fs::canonicalize(path).ok().map(strip_extended_prefix)
}

fn strip_extended_prefix(path: PathBuf) -> PathBuf {
    let text = path.to_string_lossy();
    let chars: Vec<char> = text.chars().collect();
    if chars.len() >= 4 && chars[0] == '\\' && chars[1] == '\\' && chars[2] == '?' && chars[3] == '\\' {
        PathBuf::from(chars[4..].iter().collect::<String>())
    } else {
        path
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp() -> PathBuf {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("taskboard-src-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn prefers_nested_database() {
        let root = temp();
        let harness = root.join(".harness");
        fs::create_dir_all(&harness).unwrap();
        fs::write(harness.join("harness.db"), b"not a real db").unwrap();
        fs::write(root.join("tasks.json"), b"{}").unwrap();
        let resolved = resolve_source(&root, true).unwrap();
        assert_eq!(resolved, harness);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn missing_project_is_chinese_error() {
        let err = resolve_source(Path::new("E:/definitely-missing-taskboard-src"), true).unwrap_err();
        assert!(err.contains("项目目录不存在"));
    }

    #[test]
    fn root_database_when_nested_missing() {
        let root = temp();
        fs::write(root.join("harness.db"), b"not a real db").unwrap();
        let resolved = resolve_source(&root, true).unwrap();
        assert_eq!(resolved, root);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn existing_db_does_not_fallback_to_json() {
        let root = temp();
        fs::write(root.join("harness.db"), b"not sqlite").unwrap();
        fs::write(
            root.join("tasks.json"),
            r#"{"project":"伪装项目","tasks":[{"id":"t-1","status":"pending"}]}"#,
        )
        .unwrap();
        let result = snapshot(Some(&root), None);
        assert_eq!(result["files"], json!({}));
        let errors = result["contract"]["errors"].as_array().unwrap();
        assert!(!errors.is_empty());
        assert!(errors[0].as_str().unwrap().contains("harness.db"), "{result}");
        assert_ne!(result["snapshot"]["meta"]["project"], "伪装项目");
        assert_eq!(result["snapshot"]["tasks"], json!([]));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn schema_mismatch_does_not_read_adjacent_json() {
        let root = temp();
        let conn = rusqlite::Connection::open(root.join("harness.db")).unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO meta VALUES ('schema_version', '9');
            "#,
        )
        .unwrap();
        drop(conn);
        fs::write(root.join("tasks.json"), r#"{"project":"伪装项目","tasks":[]}"#).unwrap();
        let result = snapshot(Some(&root), None);
        assert_eq!(result["files"], json!({}));
        let blob = result["contract"]["errors"].as_array().unwrap()[0].as_str().unwrap();
        assert!(blob.contains("schema_version=9"), "{result}");
        assert_ne!(result["snapshot"]["meta"]["project"], "伪装项目");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn missing_db_does_not_read_json() {
        let root = temp();
        fs::write(
            root.join("tasks.json"),
            r#"{"project":"伪装项目","tasks":[{"id":"t-1","status":"pending"}]}"#,
        )
        .unwrap();
        let result = snapshot(Some(&root), None);
        assert_eq!(result["files"], json!({}));
        assert!(result["snapshot"].is_null());
        let blob = result["contract"]["errors"].as_array().unwrap()[0].as_str().unwrap();
        assert!(blob.contains("禁止回退"), "{result}");
        assert!(blob.contains("harness.db"), "{result}");
        let _ = fs::remove_dir_all(root);
    }
}
