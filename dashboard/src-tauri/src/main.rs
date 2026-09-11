#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;

#[derive(Serialize)]
struct HarnessPayload {
    path: String,
    files: HashMap<String, String>,
}

fn resolve_source(path: &Path) -> PathBuf {
    if path.file_name().is_some_and(|name| name == ".harness") {
        return path.to_path_buf();
    }
    let nested = path.join(".harness");
    if nested.join("tasks.json").is_file() || !path.join("tasks.json").is_file() {
        nested
    } else {
        path.to_path_buf()
    }
}

fn has_tasks(path: &Path) -> bool {
    path.join("tasks.json").is_file() || path.join(".harness").join("tasks.json").is_file()
}

fn probe_candidates() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        out.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let dir = dir.to_path_buf();
            if !out.iter().any(|p| p == &dir) {
                out.push(dir);
            }
        }
    }
    out
}

#[tauri::command]
async fn pick_harness_dir() -> Result<Option<String>, String> {
    // Native IFileDialog on a worker STA thread.
    // tauri-plugin-dialog::blocking_pick_folder on the UI thread deadlocks Win32
    // and freezes the whole webview, so tabs and the status rail stop clicking.
    let picked = tauri::async_runtime::spawn_blocking(|| {
        rfd::FileDialog::new()
            .set_title("选择项目任务目录")
            .pick_folder()
    })
    .await
    .map_err(|err| err.to_string())?;
    Ok(picked.map(|path| path.to_string_lossy().into_owned()))
}

#[tauri::command]
fn probe_harness_dir() -> Option<String> {
    for path in probe_candidates() {
        if has_tasks(&path) {
            return Some(resolve_source(&path).to_string_lossy().into_owned());
        }
    }
    None
}

#[tauri::command]
fn read_harness(path: String) -> Result<HarnessPayload, String> {
    let source = resolve_source(Path::new(&path));
    let tasks_path = source.join("tasks.json");
    if !tasks_path.is_file() {
        return Err(format!("该目录没有 tasks.json: {}", source.display()));
    }
    let mut files = HashMap::new();
    files.insert(
        "tasks.json".to_string(),
        fs::read_to_string(&tasks_path).map_err(|err| err.to_string())?,
    );
    for name in ["evidence.jsonl", "reviews.jsonl", "progress.txt", "board.json"] {
        let file = source.join(name);
        if file.is_file() {
            if let Ok(text) = fs::read_to_string(&file) {
                files.insert(name.to_string(), text);
            }
        }
    }
    Ok(HarnessPayload {
        path: source.to_string_lossy().into_owned(),
        files,
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            pick_harness_dir,
            probe_harness_dir,
            read_harness
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
