resource "google_monitoring_notification_channel" "email" {
  for_each     = toset(var.alert_emails)
  display_name = "Realtoruch operations"
  type         = "email"
  labels       = { email_address = each.value }
}
resource "google_monitoring_uptime_check_config" "api" {
  count        = var.enable_uptime_monitoring ? 1 : 0
  display_name = "Realtoruch public API readiness"
  timeout      = "10s"
  period       = "60s"
  http_check {
    path         = "/readyz"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }
  monitored_resource {
    type   = "uptime_url"
    labels = { project_id = var.project_id, host = var.api_domain }
  }
}
resource "google_monitoring_alert_policy" "uptime" {
  count                 = var.enable_uptime_monitoring ? 1 : 0
  display_name          = "Realtoruch API unavailable for 5 minutes"
  combiner              = "OR"
  notification_channels = [for channel in google_monitoring_notification_channel.email : channel.name]
  conditions {
    display_name = "Readiness failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.api[0].uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_FRACTION_TRUE"
      }
      trigger { count = 1 }
    }
  }
}
resource "google_monitoring_custom_service" "api" {
  service_id   = "${var.name}-api"
  display_name = "Realtoruch API"
}
resource "google_monitoring_slo" "availability" {
  count               = var.enable_uptime_monitoring ? 1 : 0
  service             = google_monitoring_custom_service.api.service_id
  slo_id              = "availability-95"
  display_name        = "95% availability over rolling 30 days"
  goal                = 0.95
  rolling_period_days = 30
  windows_based_sli {
    window_period          = "60s"
    good_bad_metric_filter = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.api[0].uptime_check_id}\""
  }
}
resource "google_monitoring_alert_policy" "backlog" {
  display_name          = "Rental ingestion backlog older than one hour"
  combiner              = "OR"
  notification_channels = [for channel in google_monitoring_notification_channel.email : channel.name]
  conditions {
    display_name = "Oldest unacknowledged event"
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/oldest_unacked_message_age\" AND resource.label.subscription_id=\"${google_pubsub_subscription.dataflow.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 3600
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }
}
