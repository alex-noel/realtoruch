resource "google_storage_bucket" "web" {
  name                        = "${var.project_id}-${var.name}-web"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }
  versioning { enabled = true }
  lifecycle_rule {
    condition { num_newer_versions = 3 }
    action { type = "Delete" }
  }
}
# This bucket is exclusively for the public, compiled frontend. Never upload raw observations or secrets.
resource "google_storage_bucket_iam_member" "public_web" {
  bucket = google_storage_bucket.web.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
resource "google_compute_backend_bucket" "web" {
  name        = "${var.name}-web"
  bucket_name = google_storage_bucket.web.name
  enable_cdn  = true
  cdn_policy {
    cache_mode  = "USE_ORIGIN_HEADERS"
    client_ttl  = 3600
    default_ttl = 3600
    max_ttl     = 86400
  }
}
resource "google_compute_global_address" "web" { name = "${var.name}-web" }
resource "google_compute_url_map" "web" {
  name            = "${var.name}-web"
  default_service = google_compute_backend_bucket.web.id
}
resource "google_compute_managed_ssl_certificate" "web" {
  name = "${var.name}-web"
  managed { domains = [var.cdn_domain] }
}
resource "google_compute_target_https_proxy" "web" {
  name             = "${var.name}-web"
  url_map          = google_compute_url_map.web.id
  ssl_certificates = [google_compute_managed_ssl_certificate.web.id]
}
resource "google_compute_global_forwarding_rule" "web_https" {
  name                  = "${var.name}-web-https"
  target                = google_compute_target_https_proxy.web.id
  port_range            = "443"
  ip_address            = google_compute_global_address.web.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
resource "google_compute_url_map" "redirect" {
  name = "${var.name}-https-redirect"
  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
  }
}
resource "google_compute_target_http_proxy" "redirect" {
  name    = "${var.name}-redirect"
  url_map = google_compute_url_map.redirect.id
}
resource "google_compute_global_forwarding_rule" "redirect" {
  name                  = "${var.name}-web-http"
  target                = google_compute_target_http_proxy.redirect.id
  port_range            = "80"
  ip_address            = google_compute_global_address.web.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
resource "google_compute_global_address" "api" { name = "${var.name}-api" }
resource "google_compute_security_policy" "public_api" {
  name = "${var.name}-public-api"
  rule {
    action   = "throttle"
    priority = 900
    match {
      expr {
        expression = "request.path.startsWith('/v1/auth/')"
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 20
        interval_sec = 60
      }
    }
  }
  rule {
    action   = "throttle"
    priority = 1000
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 120
        interval_sec = 60
      }
    }
    description = "Free reads with a bounded per-IP request budget"
  }
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
  }
}
