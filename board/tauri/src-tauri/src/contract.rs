const FENCE: &str = "```";

use regex::Regex;
use serde_json::{json, Map, Value};
use std::sync::OnceLock;

const STATES: [&str; 6] = [
    "pending",
    "active",
    "evidence_ready",
    "passed",
    "blocked",
    "regressed",
];
const PROSE_LABELS: [&str; 9] = [
    "目标", "技术栈", "进展", "状态", "原因", "下一步", "验证结论", "评审结论", "规格评审结论",
];

pub fn validate_snapshot(
    snap: &Value,
    database: bool,
    i18n_present: bool,
    files: Option<&Map<String, Value>>,
) -> Value {
    let mut errors = Vec::new();
    let mut counts = json!({"tasks": 0, "evidence": 0, "reviews": 0});
    if i18n_present {
        errors.push("board.i18n.json：禁止看板翻译文件，请在任务原字段写中文".into());
    }
    if !database {
        if let Some(files) = files {
            for name in ["tasks.json", "evidence.jsonl", "reviews.jsonl", "progress.txt"] {
                if !files.contains_key(name) {
                    errors.push(format!("{name}：缺少契约文件；无记录的证据/评审文件可以为空"));
                }
            }
        }
    }
    let meta = snap.get("meta").cloned().unwrap_or_else(|| json!({}));
    forbidden(&meta, if database { "meta" } else { "tasks.json" }, &mut errors);
    for key in ["project", "description"] {
        let location = if database { format!("meta.{key}") } else { format!("tasks.json.{key}") };
        prose(meta.get(key), &location, &mut errors);
    }
    match snap.get("tasks").and_then(Value::as_array) {
        None => errors.push(if database {
            "snapshot.tasks：必须为任务数组，不能省略".into()
        } else {
            "tasks.json.tasks：必须为任务数组，不能省略".into()
        }),
        Some(rows) => {
            counts["tasks"] = json!(rows.len());
            let mut ids = Vec::new();
            for (index, row) in rows.iter().enumerate() {
                let location = if database {
                    format!("tasks[{index}]")
                } else {
                    format!("tasks.json.tasks[{index}]")
                };
                task(row, &location, false, &mut ids, &mut errors);
            }
        }
    }
    validate_records(
        snap.get("evidence").and_then(Value::as_array).cloned().unwrap_or_default(),
        "evidence",
        "summary",
        database,
        files.and_then(|map| map.get("evidence.jsonl").and_then(Value::as_str)),
        &mut counts,
        &mut errors,
    );
    validate_records(
        snap.get("reviews").and_then(Value::as_array).cloned().unwrap_or_default(),
        "reviews",
        "reason",
        database,
        files.and_then(|map| map.get("reviews.jsonl").and_then(Value::as_str)),
        &mut counts,
        &mut errors,
    );
    validate_progress(snap.get("progress").and_then(Value::as_str).unwrap_or(""), &mut errors);
    if !database {
        if let Some(board) = snap.get("board") {
            map_prose(board, "board.json", &mut errors);
        }
    }
    json!({"errors": errors, "counts": counts})
}

fn validate_records(
    rows: Vec<Value>,
    table: &str,
    field: &str,
    database: bool,
    raw: Option<&str>,
    counts: &mut Value,
    errors: &mut Vec<String>,
) {
    if !database {
        if let Some(text) = raw {
            let filename = if table == "evidence" { "evidence.jsonl" } else { "reviews.jsonl" };
            let mut count = 0;
            for (number, line) in text.trim_start_matches('\u{feff}').lines().enumerate() {
                if line.trim().is_empty() { continue; }
                let location = format!("{}:{}", filename, number + 1);
                match serde_json::from_str::<Value>(line) {
                    Ok(Value::Object(map)) => {
                        forbidden(&Value::Object(map.clone()), &location, errors);
                        if map.contains_key("_comment") {
                            if map.len() != 1 {
                                errors.push(format!("{location}：注释必须是仅含 _comment 的对象，不能混入业务记录"));
                            } else {
                                prose(map.get("_comment"), &format!("{location}._comment"), errors);
                            }
                            continue;
                        }
                        count += 1;
                        prose(map.get(field), &format!("{location}.{field}"), errors);
                    }
                    _ => errors.push(format!("{location}：JSON 格式错误")),
                }
            }
            counts[table] = json!(count);
            return;
        }
    }
    let mut count = 0;
    for (index, row) in rows.iter().enumerate() {
        let location = format!("{table}[{index}]");
        forbidden(row, &location, errors);
        let payload = row.get("payload").unwrap_or(row);
        if payload.get("_comment").is_some() && payload.as_object().map(|m| m.len() == 1).unwrap_or(false) {
            prose(payload.get("_comment"), &format!("{location}._comment"), errors);
            continue;
        }
        count += 1;
        prose(payload.get(field).or_else(|| row.get(field)), &format!("{location}.{field}"), errors);
    }
    counts[table] = json!(count);
}

fn task(value: &Value, location: &str, child: bool, ids: &mut Vec<String>, errors: &mut Vec<String>) {
    let Some(obj) = value.as_object() else {
        errors.push(format!("{location}：任务必须是对象，bundle 不接受 ID 字符串数组"));
        return;
    };
    forbidden(value, location, errors);
    let identifier = obj.get("id").and_then(Value::as_str).unwrap_or("");
    if identifier.trim().is_empty() || ids.iter().any(|id| id == identifier) {
        errors.push(format!("{location}.id：任务编号必须为非空、不重复的字符串"));
    } else {
        ids.push(identifier.to_string());
    }
    let required: &[&str] = if child { &["desc"] } else { &["name", "desc", "reason", "next"] };
    for key in required {
        prose(obj.get(*key), &format!("{location}.{key}"), errors);
    }
    if child {
        for key in ["name", "reason", "next"] {
            if obj.contains_key(key) {
                prose(obj.get(key), &format!("{location}.{key}"), errors);
            }
        }
    }
    if !child || obj.contains_key("status") {
        let status = obj.get("status").and_then(Value::as_str);
        if status.map(|item| !STATES.contains(&item)).unwrap_or(true) {
            errors.push(format!("{location}.status：必须使用规定的英文状态枚举"));
        }
    }
    if child {
        let verify = obj.get("verify").and_then(Value::as_str).unwrap_or("");
        if verify.trim().is_empty() {
            errors.push(format!("{location}.verify：束内任务必须提供非空验证命令字符串"));
        }
    }
    for key in ["wave", "title", "description"] {
        if obj.contains_key(key) {
            prose(obj.get(key), &format!("{location}.{key}"), errors);
        }
    }
    if let Some(phase) = obj.get("phase") {
        if !phase.is_number() {
            prose(Some(phase), &format!("{location}.phase"), errors);
        }
    }
    if let Some(bundle) = obj.get("bundle") {
        match bundle.as_array() {
            Some(items) if !items.is_empty() => {
                for (index, member) in items.iter().enumerate() {
                    task(member, &format!("{location}.bundle[{index}]"), true, ids, errors);
                }
            }
            _ => errors.push(format!("{location}.bundle：必须为非空任务对象数组")),
        }
    }
}

fn prose(value: Option<&Value>, location: &str, errors: &mut Vec<String>) {
    let Some(Value::String(text)) = value else {
        errors.push(format!("{location}：必须是非空中文说明字符串（机器标识可保留原文）"));
        return;
    };
    if text.trim().is_empty() || !has_cjk(text) {
        errors.push(format!("{location}：必须是非空中文说明字符串（机器标识可保留原文）"));
        return;
    }
    if placeholder().is_match(text.trim()) {
        errors.push(format!("{location}：必须替换模板占位符"));
    }
}

fn forbidden(value: &Value, location: &str, errors: &mut Vec<String>) {
    match value {
        Value::Object(map) => {
            for (key, item) in map {
                if key.ends_with("_zh") {
                    errors.push(format!("{location}.{key}：禁止旁挂翻译字段，请直接填写原字段"));
                }
                forbidden(item, &format!("{location}.{key}"), errors);
            }
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                forbidden(item, &format!("{location}[{index}]"), errors);
            }
        }
        _ => {}
    }
}

fn validate_progress(progress: &str, errors: &mut Vec<String>) {
    let mut narrative = 0;
    let mut fence: Option<String> = None;
    for (number, raw) in progress.trim_start_matches('\u{feff}').lines().enumerate() {
        let line = raw.trim();
        let location = format!("progress.txt:{}", number + 1);
        if line.starts_with(FENCE) || line.starts_with("~~~") {
            let marker = &line[..3];
            match &fence {
                None => fence = Some(marker.to_string()),
                Some(open) if line.starts_with(open) => fence = None,
                _ => {}
            }
            continue;
        }
        if fence.is_some() || line.is_empty() || rule().is_match(line) || protocol().is_match(line) {
            continue;
        }
        narrative += 1;
        let content = leading().replace(line, "");
        let parts: Vec<&str> = content.splitn(2, |c| c == '：' || c == ':').collect();
        if parts.len() == 2 && PROSE_LABELS.contains(&parts[0].trim()) {
            prose(Some(&Value::String(parts[1].trim().to_string())), &location, errors);
        } else {
            prose(Some(&Value::String(content.to_string())), &location, errors);
        }
    }
    if fence.is_some() {
        errors.push("progress.txt：命令代码围栏未闭合".into());
    }
    if narrative == 0 {
        errors.push("progress.txt：必须包含中文进度叙事，不能只有机器输出或空白".into());
    }
}

fn map_prose(value: &Value, location: &str, errors: &mut Vec<String>) {
    match value {
        Value::Object(map) => {
            forbidden(value, location, errors);
            for (key, item) in map {
                if ["where", "what", "why", "see", "problem", "name", "desc", "description"].contains(&key.as_str())
                    && !item.is_object()
                    && !item.is_array()
                {
                    prose(Some(item), &format!("{location}.{key}"), errors);
                }
                map_prose(item, &format!("{location}.{key}"), errors);
            }
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                map_prose(item, &format!("{location}[{index}]"), errors);
            }
        }
        _ => {}
    }
}

fn has_cjk(text: &str) -> bool {
    text.chars().any(|ch| (0x3400..=0x9FFF).contains(&(ch as u32)))
}

fn placeholder() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\{\{.*?\}\}|^<[^>]+>$").unwrap())
}

fn protocol() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?:HARNESS_STATUS: \S+ (?:IN_PROGRESS|COMPLETE|BLOCKED)|PROGRESS: \d+/\d+|EXIT_SIGNAL: (?:false|true))$").unwrap())
}

fn rule() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^[\-=*_\s]+$").unwrap())
}

fn leading() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^[#*\-\s]+").unwrap())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn database_mode_does_not_require_json_files() {
        let snap = json!({
            "meta": {"project": "测试项目", "description": "说明文字"},
            "tasks": [{"id": "t-1", "name": "任务名称", "desc": "任务描述", "reason": "原因说明", "next": "下一步", "status": "pending"}],
            "evidence": [{"id": "ev-1", "summary": "证据摘要"}],
            "reviews": [{"id": "rv-1", "reason": "评审理由"}],
            "progress": "## 2026-09-13 | t-1 | 执行\n- 状态：已验证中文"
        });
        let result = validate_snapshot(&snap, true, false, None);
        assert!(result["errors"].as_array().unwrap().is_empty(), "{result}");
    }

    #[test]
    fn rejects_zh_and_i18n() {
        let snap = json!({
            "meta": {"project": "测试项目", "description": "说明文字"},
            "tasks": [{"id": "t-1", "name": "任务名称", "desc": "任务描述", "reason": "原因说明", "next": "下一步", "status": "pending", "name_zh": "x"}],
            "evidence": [],
            "reviews": [],
            "progress": "中文进度叙事一行"
        });
        let result = validate_snapshot(&snap, true, true, None);
        let errors = result["errors"].as_array().unwrap().iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join("\n");
        assert!(errors.contains("board.i18n.json"));
        assert!(errors.contains("name_zh"));
    }
}
