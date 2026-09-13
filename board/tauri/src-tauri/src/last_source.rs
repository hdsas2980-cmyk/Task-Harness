use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

pub static LAST_SOURCE_LOCK: Mutex<()> = Mutex::new(());

pub fn last_source_path() -> PathBuf {
    if let Ok(env_path) = std::env::var("TASK_HARNESS_LAST_SOURCE") {
        let trimmed = env_path.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    let appdata = std::env::var("APPDATA").unwrap_or_else(|_| {
        let home = std::env::var("USERPROFILE").unwrap_or_else(|_| ".".into());
        PathBuf::from(home)
            .join("AppData")
            .join("Roaming")
            .to_string_lossy()
            .into_owned()
    });
    PathBuf::from(appdata)
        .join("TaskHarness")
        .join("TaskBoard")
        .join("last-source.txt")
}

pub fn load_last_source() -> Option<String> {
    let text = fs::read_to_string(last_source_path()).ok()?;
    let trimmed = text.trim().trim_start_matches('\u{feff}');
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

pub fn save_last_source(source: &Path) {
    let path = last_source_path();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let tmp = path.with_extension("txt.tmp");
    let payload = format!("{}\n", source.display());
    if fs::write(&tmp, payload).is_ok() {
        if fs::rename(&tmp, &path).is_err() {
            let _ = fs::remove_file(&tmp);
        }
    }
}

#[cfg(test)]
pub struct IsolatedLastSource {
    _lock: std::sync::MutexGuard<'static, ()>,
    previous: Option<String>,
    pub dir: PathBuf,
}

#[cfg(test)]
impl IsolatedLastSource {
    pub fn new() -> Self {
        use std::time::{SystemTime, UNIX_EPOCH};
        let lock = LAST_SOURCE_LOCK.lock().unwrap();
        let previous = std::env::var("TASK_HARNESS_LAST_SOURCE").ok();
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("taskboard-last-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        std::env::set_var("TASK_HARNESS_LAST_SOURCE", dir.join("last-source.txt"));
        Self {
            _lock: lock,
            previous,
            dir,
        }
    }
}

#[cfg(test)]
impl Drop for IsolatedLastSource {
    fn drop(&mut self) {
        match &self.previous {
            Some(value) => std::env::set_var("TASK_HARNESS_LAST_SOURCE", value),
            None => std::env::remove_var("TASK_HARNESS_LAST_SOURCE"),
        }
        let _ = fs::remove_dir_all(&self.dir);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn env_override_is_path_only() {
        let _iso = IsolatedLastSource::new();
        save_last_source(Path::new(r"E:\demo\.harness"));
        assert_eq!(load_last_source().as_deref(), Some(r"E:\demo\.harness"));
    }
}
