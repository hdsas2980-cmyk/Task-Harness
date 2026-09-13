use std::path::PathBuf;
use std::sync::Mutex;

pub mod assets;
pub mod contract;
pub mod db;
pub mod files;
pub mod http;
pub mod last_source;
pub mod picker;
pub mod sessions;
pub mod source;

pub struct BoardState {
    source: Mutex<Option<PathBuf>>,
}

impl BoardState {
    pub fn new() -> Self {
        Self {
            source: Mutex::new(None),
        }
    }

    pub fn current_source(&self) -> Option<PathBuf> {
        self.source.lock().ok().and_then(|guard| guard.clone())
    }

    pub fn set_source(&self, path: PathBuf) {
        if let Ok(mut guard) = self.source.lock() {
            *guard = Some(path.clone());
        }
        last_source::save_last_source(&path);
    }

    pub fn restore_last_source(&self) {
        let Some(raw) = last_source::load_last_source() else {
            return;
        };
        if let Ok(path) = source::bind_source(&raw) {
            if let Ok(mut guard) = self.source.lock() {
                *guard = Some(path);
            }
        }
    }
}

impl Default for BoardState {
    fn default() -> Self {
        Self::new()
    }
}

pub fn native_error(title: &str, message: &str) {
    #[cfg(windows)]
    {
        windows_message_box(title, message);
    }
    #[cfg(not(windows))]
    {
        eprintln!("{title}: {message}");
    }
}

#[cfg(windows)]
fn windows_message_box(title: &str, message: &str) {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;

    fn wide(text: &str) -> Vec<u16> {
        OsStr::new(text).encode_wide().chain(std::iter::once(0)).collect()
    }

    #[link(name = "user32")]
    extern "system" {
        fn MessageBoxW(
            hwnd: *mut core::ffi::c_void,
            text: *const u16,
            caption: *const u16,
            flags: u32,
        ) -> i32;
    }

    const MB_ICONERROR: u32 = 0x00000010;
    let text = wide(message);
    let caption = wide(title);
    unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            text.as_ptr(),
            caption.as_ptr(),
            MB_ICONERROR,
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn restores_existing_last_source() {
        let iso = last_source::IsolatedLastSource::new();
        let harness = iso.dir.join("proj").join(".harness");
        fs::create_dir_all(&harness).unwrap();
        fs::write(harness.join("harness.db"), b"not sqlite").unwrap();
        last_source::save_last_source(&harness);
        let state = BoardState::new();
        assert!(state.current_source().is_none());
        state.restore_last_source();
        assert_eq!(state.current_source().as_deref(), Some(harness.as_path()));
    }

    #[test]
    fn invalid_last_source_is_ignored() {
        let _iso = last_source::IsolatedLastSource::new();
        last_source::save_last_source(std::path::Path::new("E:/definitely-missing-taskboard-restore"));
        let state = BoardState::new();
        state.restore_last_source();
        assert!(state.current_source().is_none());
    }
}
