#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod policy;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri::webview::{NewWindowResponse, PermissionResponse};

fn main() {
    let endpoints = policy::Endpoints::parse(
        env!("FOLIO_DESKTOP_APP_URL"),
        env!("FOLIO_DESKTOP_API_BASE_URL"),
        cfg!(debug_assertions),
    ).unwrap_or_else(|message| { eprintln!("Folio configuration: {message}"); std::process::exit(2) });

    tauri::Builder::default()
        // No invoke_handler, shell, filesystem, process, HTTP proxy or remote IPC plugin.
        .setup(move |app| {
            let builder = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(endpoints.app.clone()))
                .title("Folio")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1024.0, 720.0)
                .resizable(true)
                .incognito(false)
                .devtools(cfg!(debug_assertions))
                .on_navigation(move |url| endpoints.allows(url))
                .on_new_window(|_, _| NewWindowResponse::Deny)
                .on_download(|_, _| false)
                .on_permission_request(|_, _| PermissionResponse::Deny);

            #[cfg(target_os = "linux")]
            let builder = {
                let suffix = if cfg!(debug_assertions) { "webview-dev" } else { "webview" };
                let directory = app.path().app_local_data_dir()?.join(suffix);
                std::fs::create_dir_all(&directory)?;
                builder.data_directory(directory)
            };
            #[cfg(target_os = "macos")]
            let builder = builder.data_store_identifier([
                0x46, 0x6f, 0x6c, 0x69, 0x6f, 0x2d, 0x44, 0x65,
                0x73, 0x6b, 0x74, 0x6f, 0x70, 0x00, 0x00,
                if cfg!(debug_assertions) { 0x02 } else { 0x01 },
            ]);
            builder.build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Folio could not start its desktop window");
}
