#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;
use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

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

#[tauri::command]
fn pick_harness_dir(app: AppHandle) -> Result<Option<String>, String> {
    let picked = app
        .dialog()
        .file()
        .set_title("选择项目任务目录")
        .blocking_pick_folder();
    Ok(picked.map(|path| path.to_string()))
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
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![pick_harness_dir, read_harness])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
