use tauri::Url;

pub struct Endpoints { pub app: Url }
impl Endpoints {
    pub fn parse(app: &str, api: &str, development: bool) -> Result<Self, String> {
        let app = Url::parse(app).map_err(|_| "Application URL is invalid")?;
        let api = Url::parse(api).map_err(|_| "API URL is invalid")?;
        for url in [&app, &api] {
            if !url.username().is_empty() || url.password().is_some() || url.query().is_some() || url.fragment().is_some() {
                return Err("Endpoint credentials, query strings and fragments are forbidden".into());
            }
            let dev_origin = url.origin().ascii_serialization() == "http://127.0.0.1:5176";
            let host = url.host_str().unwrap_or("");
            let loopback = host == "localhost" || host == "127.0.0.1" || host == "[::1]" || host.ends_with(".localhost") || host.starts_with("127.") || host.ends_with(".invalid");
            if !(development && dev_origin) && (url.scheme() != "https" || loopback || host.is_empty()) {
                return Err("Use the pinned HTTPS deployment; loopback is development-only".into());
            }
        }
        if app.origin() != api.origin() || api.path() != "/" {
            return Err("The React client requires the API at the same origin's /v1 path".into());
        }
        Ok(Self { app })
    }
    pub fn allows(&self, candidate: &Url) -> bool {
        candidate.origin() == self.app.origin()
            && candidate.scheme() == self.app.scheme()
            && candidate.username().is_empty()
            && candidate.password().is_none()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn refuses_cross_origin_api() {
        assert!(Endpoints::parse("https://folio.example", "https://api.folio.example", false).is_err());
    }
    #[test]
    fn allows_only_exact_origin_navigation() {
        let endpoints = Endpoints::parse("https://folio.example/demo", "https://folio.example", false).unwrap();
        assert!(endpoints.allows(&Url::parse("https://folio.example/review").unwrap()));
        for target in ["https://folio.example.evil.test", "http://folio.example", "file:///etc/passwd", "https://other.example"] {
            assert!(!endpoints.allows(&Url::parse(target).unwrap()));
        }
    }
    #[test]
    fn loopback_is_not_a_release_deployment() {
        assert!(Endpoints::parse("http://127.0.0.1:5176", "http://127.0.0.1:5176", false).is_err());
        assert!(Endpoints::parse("http://127.0.0.1:5176", "http://127.0.0.1:5176", true).is_ok());
    }
}
