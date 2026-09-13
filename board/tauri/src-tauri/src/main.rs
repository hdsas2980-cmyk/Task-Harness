#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Arc;

use tauri::{WebviewUrl, WebviewWindowBuilder};

use task_board::{http, BoardState};

fn main() {
    let state = Arc::new(BoardState::new());
    state.restore_last_source();
    let port = match http::bind_loopback(Arc::clone(&state)) {
        Ok(port) => port,
        Err(err) => {
            task_board::native_error("TaskBoard", &err);
            std::process::exit(1);
        }
    };
    let url = format!("http://127.0.0.1:{port}/");
    let parsed = match url.parse() {
        Ok(value) => value,
        Err(_) => {
            task_board::native_error("TaskBoard", "无法解析本地看板地址");
            std::process::exit(1);
        }
    };
    let result = tauri::Builder::default()
        .setup(move |app| {
            match WebviewWindowBuilder::new(app, "main", WebviewUrl::External(parsed))
                .title("Task Harness 看板")
                .inner_size(1280.0, 860.0)
                .min_inner_size(960.0, 640.0)
                .build()
            {
                Ok(_) => Ok(()),
                Err(err) => {
                    let message = webview_error(&err.to_string());
                    task_board::native_error("TaskBoard", &message);
                    Err(err.into())
                }
            }
        })
        .run(tauri::generate_context!());
    if let Err(err) = result {
        task_board::native_error("TaskBoard", &webview_error(&err.to_string()));
        std::process::exit(1);
    }
}

fn webview_error(raw: &str) -> String {
    let lower = raw.to_ascii_lowercase();
    if lower.contains("webview2") || lower.contains("web view 2") || lower.contains("edgewebview") {
        return String::from(
            "本机未安装 Microsoft Edge WebView2 Runtime，TaskBoard 无法显示看板。\n\n本程序不携带、不下载、不安装 WebView2。请从微软官方 Evergreen Runtime 安装系统 WebView2 后再打开：\nhttps://developer.microsoft.com/microsoft-edge/webview2/",
        );
    }
    if raw.trim().is_empty() {
        "无法启动看板窗口。".into()
    } else {
        format!("无法启动看板窗口：{raw}")
    }
}
