use std::io::Cursor;
use std::sync::Arc;
use std::thread;

use serde_json::{json, Value};
use tiny_http::{Header, Request, Response, Server, StatusCode};

use crate::{assets, last_source, picker, sessions, source, BoardState};

pub const PORT_MIN: u16 = 8765;
pub const PORT_MAX: u16 = 8799;

pub struct HttpResponse {
    pub status: u16,
    pub content_type: &'static str,
    pub body: Vec<u8>,
}

pub fn bind_loopback(state: Arc<BoardState>) -> Result<u16, String> {
    for port in PORT_MIN..=PORT_MAX {
        let addr = format!("127.0.0.1:{port}");
        match Server::http(&addr) {
            Ok(server) => {
                thread::spawn(move || run_server(server, state));
                return Ok(port);
            }
            Err(_) => continue,
        }
    }
    Err("无法在 127.0.0.1:8765-8799 找到空闲端口".into())
}

fn run_server(server: Server, state: Arc<BoardState>) {
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        for request in server.incoming_requests() {
            let state = Arc::clone(&state);
            thread::spawn(move || serve_one(&state, request));
        }
    }));
    if result.is_err() {
        crate::native_error(
            "TaskBoard",
            "看板 HTTP 服务异常退出。窗口将关闭，任务文件未被写入。",
        );
        std::process::exit(1);
    }
}

fn serve_one(state: &BoardState, mut request: Request) {
    let method = request.method().as_str().to_string();
    let url = request.url().to_string();
    let mut body = Vec::new();
    if method != "GET" && method != "HEAD" {
        let _ = std::io::Read::read_to_end(request.as_reader(), &mut body);
        if body.len() > 1_000_000 {
            let response = json_response(400, &json!({"error": "请求过大"}));
            let _ = request.respond(to_tiny(response));
            return;
        }
    }
    let handled = handle(state, &method, &url, &body);
    let _ = request.respond(to_tiny(handled));
}

pub fn handle(state: &BoardState, method: &str, url: &str, body: &[u8]) -> HttpResponse {
    let path = normalize_path(url);
    let method = method.to_ascii_uppercase();
    match method.as_str() {
        "GET" | "HEAD" => handle_get(state, &path, method == "HEAD"),
        "POST" => handle_post(state, &path, body),
        "PUT" | "PATCH" | "DELETE" => write_rejected(),
        _ => write_rejected(),
    }
}

fn handle_get(state: &BoardState, path: &str, head: bool) -> HttpResponse {
    if path == "/" || path == "/index.html" || path == "/task-harness.html" {
        return bytes_response(200, "text/html; charset=utf-8", assets::index_html(), head);
    }
    if path == "/app.js" {
        return bytes_response(200, "text/javascript; charset=utf-8", assets::app_js(), head);
    }
    if path == "/api/snapshot" {
        return json_response(200, &current_snapshot(state));
    }
    if path == "/api/sessions" {
        let source = state.current_source();
        return json_response(200, &sessions::list_session_catalog(source.as_deref(), None));
    }
    if path.starts_with("/api/") {
        return json_response(404, &json!({"error": "Not found"}));
    }
    text_response(404, "Not found")
}

fn handle_post(state: &BoardState, path: &str, body: &[u8]) -> HttpResponse {
    if path == "/api/source" {
        return post_source(state, body);
    }
    if path == "/api/pick-dir" {
        return post_pick_dir();
    }
    write_rejected()
}

fn post_source(state: &BoardState, body: &[u8]) -> HttpResponse {
    let parsed = match parse_object(body) {
        Ok(value) => value,
        Err(err) => return json_response(400, &json!({"error": err})),
    };
    let raw = parsed
        .get("path")
        .or_else(|| parsed.get("cwd"))
        .or_else(|| parsed.get("source"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    match source::bind_source(&raw) {
        Ok(path) => {
            state.set_source(path);
            json_response(200, &current_snapshot(state))
        }
        Err(err) => json_response(400, &json!({"error": err})),
    }
}

fn post_pick_dir() -> HttpResponse {
    match picker::pick_directory("选择 harness / 项目目录") {
        Ok(Some(path)) => json_response(
            200,
            &json!({"path": path.to_string_lossy(), "cancelled": false}),
        ),
        Ok(None) => json_response(200, &json!({"cancelled": true})),
        Err(err) => {
            let busy = err.contains("已有目录对话框打开");
            json_response(
                if busy { 409 } else { 400 },
                &json!({"error": err, "cancelled": true}),
            )
        }
    }
}

fn current_snapshot(state: &BoardState) -> Value {
    source::snapshot(
        state.current_source().as_deref(),
        last_source::load_last_source(),
    )
}

fn parse_object(body: &[u8]) -> Result<Value, String> {
    if body.len() > 1_000_000 {
        return Err("请求过大".into());
    }
    let text = if body.is_empty() {
        "{}".to_string()
    } else {
        String::from_utf8(body.to_vec()).map_err(|_| "JSON 无效".to_string())?
    };
    let trimmed = text.trim_start_matches('\u{feff}');
    let value: Value =
        serde_json::from_str(if trimmed.trim().is_empty() { "{}" } else { trimmed })
            .map_err(|_| "JSON 无效".to_string())?;
    if !value.is_object() {
        return Err("JSON 必须是对象".into());
    }
    Ok(value)
}

fn write_rejected() -> HttpResponse {
    json_response(405, &json!({"error": "只读，不写任务、证据、评审或进度"}))
}

fn json_response(status: u16, value: &Value) -> HttpResponse {
    HttpResponse {
        status,
        content_type: "application/json; charset=utf-8",
        body: json_bytes(value),
    }
}

fn json_bytes(value: &Value) -> Vec<u8> {
    let mut out = Vec::new();
    write_json(&mut out, value);
    out
}

fn write_json(out: &mut Vec<u8>, value: &Value) {
    match value {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(true) => out.extend_from_slice(b"true"),
        Value::Bool(false) => out.extend_from_slice(b"false"),
        Value::Number(number) => out.extend_from_slice(number.to_string().as_bytes()),
        Value::String(text) => write_json_string(out, text),
        Value::Array(items) => {
            out.push(b'[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(b',');
                }
                write_json(out, item);
            }
            out.push(b']');
        }
        Value::Object(map) => {
            out.push(b'{');
            for (index, (key, item)) in map.iter().enumerate() {
                if index > 0 {
                    out.push(b',');
                }
                write_json_string(out, key);
                out.push(b':');
                write_json(out, item);
            }
            out.push(b'}');
        }
    }
}

fn write_json_string(out: &mut Vec<u8>, text: &str) {
    out.push(b'"');
    for ch in text.chars() {
        match ch {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{08}' => out.extend_from_slice(b"\\b"),
            '\u{0C}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) < 0x20 => {
                let encoded = format!("\\u{:04x}", c as u32);
                out.extend_from_slice(encoded.as_bytes());
            }
            c => {
                let mut buf = [0u8; 4];
                out.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
            }
        }
    }
    out.push(b'"');
}

fn text_response(status: u16, text: &str) -> HttpResponse {
    HttpResponse {
        status,
        content_type: "text/plain; charset=utf-8",
        body: text.as_bytes().to_vec(),
    }
}

fn bytes_response(status: u16, content_type: &'static str, body: &[u8], head: bool) -> HttpResponse {
    HttpResponse {
        status,
        content_type,
        body: if head { Vec::new() } else { body.to_vec() },
    }
}

fn normalize_path(url: &str) -> String {
    let without_hash = url.split('#').next().unwrap_or(url);
    let raw = without_hash.split('?').next().unwrap_or(without_hash);
    let decoded = percent_decode(raw);
    let mut parts = Vec::new();
    for part in decoded.split('/') {
        if part.is_empty() || part == "." {
            continue;
        }
        if part == ".." {
            let _ = parts.pop();
            continue;
        }
        parts.push(part.to_string());
    }
    if parts.is_empty() {
        "/".into()
    } else {
        format!("/{}", parts.join("/"))
    }
}

fn percent_decode(input: &str) -> String {
    let bytes = input.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            if let (Some(hi), Some(lo)) = (from_hex(bytes[index + 1]), from_hex(bytes[index + 2])) {
                out.push((hi << 4) | lo);
                index += 3;
                continue;
            }
        }
        out.push(bytes[index]);
        index += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn from_hex(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

fn to_tiny(response: HttpResponse) -> Response<Cursor<Vec<u8>>> {
    let mut out = Response::new(
        StatusCode(response.status),
        Vec::new(),
        Cursor::new(response.body.clone()),
        Some(response.body.len()),
        None,
    );
    if let Ok(header) = Header::from_bytes(b"Content-Type", response.content_type.as_bytes()) {
        out.add_header(header);
    }
    if let Ok(header) = Header::from_bytes(b"Cache-Control", b"no-store") {
        out.add_header(header);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};


    fn isolated_state() -> (BoardState, crate::last_source::IsolatedLastSource) {
        let iso = crate::last_source::IsolatedLastSource::new();
        (BoardState::new(), iso)
    }
    fn unique_dir(prefix: &str) -> std::path::PathBuf {
        let unique = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("{prefix}-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn empty_source_keeps_snapshot_null() {
        let (state, _iso) = isolated_state();
        let response = handle(&state, "GET", "/api/snapshot", b"");
        assert_eq!(response.status, 200);
        let body: Value = serde_json::from_slice(&response.body).unwrap();
        assert!(body["source"].is_null());
        assert!(body["snapshot"].is_null());
        assert!(body["contract"].is_null());
        assert_eq!(body["files"], json!({}));
    }

    #[test]
    fn write_methods_are_rejected() {
        let (state, _iso) = isolated_state();
        for method in ["PUT", "PATCH", "DELETE", "POST"] {
            let path = if method == "POST" {
                "/api/unknown"
            } else {
                "/api/snapshot"
            };
            let response = handle(&state, method, path, b"{}");
            assert_eq!(response.status, 405, "{method}");
            let body = String::from_utf8(response.body).unwrap();
            assert!(body.contains("只读"));
        }
    }

    #[test]
    fn static_routes_are_embedded() {
        let (state, _iso) = isolated_state();
        let html = handle(&state, "GET", "/", b"");
        let js = handle(&state, "GET", "/app.js", b"");
        assert_eq!(html.status, 200);
        assert_eq!(js.status, 200);
        assert!(String::from_utf8_lossy(&html.body).contains("app.js"));
        assert!(String::from_utf8_lossy(&js.body).contains("/api/snapshot"));
    }

    #[test]
    fn database_mode_does_not_synthesize_tasks_json() {
        let dir = unique_dir("taskboard-http-db");
        fs::write(dir.join("harness.db"), b"not sqlite").unwrap();
        let (state, _iso) = isolated_state();
        state.set_source(dir.clone());
        let missing = handle(&state, "GET", "/tasks.json", b"");
        assert_eq!(missing.status, 404);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn json_files_are_not_served() {
        let dir = unique_dir("taskboard-http-files");
        fs::write(dir.join("tasks.json"), r#"{"tasks":[]}"#).unwrap();
        let (state, _iso) = isolated_state();
        state.set_source(dir.clone());
        let json_file = handle(&state, "GET", "/tasks.json", b"");
        let board_file = handle(&state, "GET", "/board.json", b"");
        assert_eq!(json_file.status, 404);
        assert_eq!(board_file.status, 404);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn pick_dir_busy_is_conflict() {
        let (state, _iso) = isolated_state();
        let _guard = picker::try_acquire().unwrap();
        let response = handle(&state, "POST", "/api/pick-dir", b"{}");
        assert_eq!(response.status, 409);
        let body: Value = serde_json::from_slice(&response.body).unwrap();
        assert_eq!(body["cancelled"], true);
        assert!(body["error"].as_str().unwrap().contains("已有目录对话框打开"));
    }

    #[test]
    fn loopback_ports_are_fixed_range() {
        assert_eq!(PORT_MIN, 8765);
        assert_eq!(PORT_MAX, 8799);
    }

    #[test]
    fn invalid_source_json_is_chinese_error() {
        let (state, _iso) = isolated_state();
        let response = handle(&state, "POST", "/api/source", b"[1]");
        assert_eq!(response.status, 400);
        let body: Value = serde_json::from_slice(&response.body).unwrap();
        assert!(body["error"].as_str().unwrap().contains("JSON"));
    }

    #[test]
    fn json_preserves_chinese() {
        let response = write_rejected();
        let body = String::from_utf8(response.body).unwrap();
        assert!(body.contains("只读"));
        assert!(!body.contains("\\u"), "{body}");
    }

    #[test]
    fn missing_source_is_chinese_error() {
        let (state, _iso) = isolated_state();
        let response = handle(
            &state,
            "POST",
            "/api/source",
            br#"{"path":"E:/definitely-missing-taskboard-http"}"#,
        );
        assert_eq!(response.status, 400);
        let body = String::from_utf8(response.body).unwrap();
        assert!(body.contains("项目目录不存在"));
        assert!(!body.contains("\\u"), "{body}");
    }

    #[test]
    fn restored_last_source_appears_in_snapshot() {
        let iso = crate::last_source::IsolatedLastSource::new();
        let harness = iso.dir.join("proj").join(".harness");
        fs::create_dir_all(&harness).unwrap();
        let conn = rusqlite::Connection::open(harness.join("harness.db")).unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE evidence (id TEXT PRIMARY KEY, task_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE reviews (id TEXT PRIMARY KEY, task_id TEXT, evidence_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE progress (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO meta VALUES ('schema_version', '1');
            INSERT INTO meta VALUES ('project', '"恢复来源"');
            "#,
        ).unwrap();
        drop(conn);
        crate::last_source::save_last_source(&harness);
        let state = BoardState::new();
        state.restore_last_source();
        let response = handle(&state, "GET", "/api/snapshot", b"");
        let body: Value = serde_json::from_slice(&response.body).unwrap();
        assert!(body["source"].as_str().unwrap().ends_with(".harness"));
        assert_eq!(body["snapshot"]["meta"]["project"], "恢复来源");
        assert!(body["snapshot"]["tasks"].is_array());
    }
}
