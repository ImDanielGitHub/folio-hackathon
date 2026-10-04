fn main() {
    println!("cargo:rerun-if-env-changed=FOLIO_DESKTOP_APP_URL");
    println!("cargo:rerun-if-env-changed=FOLIO_DESKTOP_API_BASE_URL");
    let development = std::env::var("PROFILE").as_deref() != Ok("release");
    let app = std::env::var("FOLIO_DESKTOP_APP_URL").unwrap_or_else(|_| {
        if development { "http://127.0.0.1:5176/".into() }
        else { panic!("Set FOLIO_DESKTOP_APP_URL to the approved HTTPS deployment before building.") }
    });
    let api = std::env::var("FOLIO_DESKTOP_API_BASE_URL").unwrap_or_else(|_| app.clone());
    for (key, value) in [("FOLIO_DESKTOP_APP_URL", app), ("FOLIO_DESKTOP_API_BASE_URL", api)] {
        assert!(!value.chars().any(char::is_control), "Endpoint must not contain control characters");
        println!("cargo:rustc-env={key}={value}");
    }
    tauri_build::build();
}
