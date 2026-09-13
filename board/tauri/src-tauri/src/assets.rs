pub fn index_html() -> &'static [u8] {
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../static/index.html"))
}

pub fn app_js() -> &'static [u8] {
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../static/app.js"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embeds_frontend_and_api_contract() {
        let html = String::from_utf8_lossy(index_html());
        let js = String::from_utf8_lossy(app_js());
        assert!(html.contains("app.js"));
        assert!(js.contains("/api/snapshot"));
        assert!(!js.contains("parseI18n"));
    }
}
