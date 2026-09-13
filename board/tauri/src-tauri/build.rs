fn main() {
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let static_dir = manifest_dir.join("../../static");
    let index = static_dir.join("index.html");
    let app_js = static_dir.join("app.js");
    for path in [&index, &app_js] {
        if !path.is_file() {
            panic!("missing embedded frontend file: {}", path.display());
        }
        let text = std::fs::read_to_string(path).expect("read frontend");
        for needle in [
            "board.i18n.json",
            "parseI18n",
            "translated(",
            "name_zh",
            "desc_zh",
            "summary_zh",
            "reason_zh",
        ] {
            if text.contains(needle) {
                panic!("{} still contains translation hook: {needle}", path.display());
            }
        }
    }
    let pkg = std::fs::read_to_string(manifest_dir.join("../package.json")).expect("package.json");
    if !pkg.contains("\"version\": \"1.0.0\"") {
        panic!("package.json version must match Cargo.toml 1.0.0");
    }
    let cargo = std::fs::read_to_string(manifest_dir.join("Cargo.toml")).expect("Cargo.toml");
    if !cargo.contains("version = \"1.0.0\"") {
        panic!("Cargo.toml version must be 1.0.0");
    }
    println!("cargo:rerun-if-changed=../../static/index.html");
    println!("cargo:rerun-if-changed=../../static/app.js");
    println!("cargo:rerun-if-changed=../package.json");
    tauri_build::build();
}
