use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};

static BUSY: AtomicBool = AtomicBool::new(false);

#[derive(Debug)]
pub struct PickerGuard;

impl Drop for PickerGuard {
    fn drop(&mut self) {
        BUSY.store(false, Ordering::SeqCst);
    }
}

pub fn try_acquire() -> Result<PickerGuard, String> {
    if BUSY.compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst).is_err() {
        return Err("已有目录对话框打开".into());
    }
    Ok(PickerGuard)
}

pub fn pick_directory(title: &str) -> Result<Option<PathBuf>, String> {
    let _guard = try_acquire()?;
    Ok(rfd::FileDialog::new().set_title(title).pick_folder())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_flight_lock() {
        let first = try_acquire().unwrap();
        let second = try_acquire().unwrap_err();
        assert!(second.contains("已有目录对话框打开"));
        drop(first);
        assert!(try_acquire().is_ok());
    }
}
