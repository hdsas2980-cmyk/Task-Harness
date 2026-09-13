use std::path::Path;

use serde_json::{json, Value};

pub fn read_files(dir: &Path, last_source: Option<String>) -> Value {
    let db_path = dir.join("harness.db");
    json!({
        "source": dir.to_string_lossy(),
        "files": {},
        "snapshot": Value::Null,
        "contract": {
            "errors": [format!("未初始化 {}，禁止回退 JSON/JSONL/TXT", db_path.display())],
            "counts": {"tasks": 0, "evidence": 0, "reviews": 0}
        },
        "last_source": last_source,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn read_files_does_not_fallback_to_json() {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("taskboard-files-{unique}"));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("tasks.json"),
            r#"{"project":"测试项目","tasks":[{"id":"t-1","status":"pending"}]}"#,
        )
        .unwrap();
        let result = read_files(&dir, None);
        assert!(result["snapshot"].is_null());
        assert_eq!(result["files"], json!({}));
        let blob = result["contract"]["errors"].as_array().unwrap()[0].as_str().unwrap();
        assert!(blob.contains("禁止回退"), "{result}");
        let _ = std::fs::remove_dir_all(dir);
    }
}
