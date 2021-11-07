resource "google_sql_database_instance" "main" {
  name                = "${var.name}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true
  settings {
    tier                  = "db-custom-1-3840"
    availability_type     = "ZONAL"
    disk_type             = "PD_SSD"
    disk_size             = 20
    disk_autoresize       = true
    disk_autoresize_limit = 100
    location_preference { zone = var.zone }
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings { retained_backups = 14 }
    }
    maintenance_window {
      day  = 7
      hour = 3
    }
    insights_config { query_insights_enabled = true }
  }
  depends_on = [google_service_networking_connection.private]
}
resource "google_sql_database" "databases" {
  for_each = toset(["rentals", "auth"])
  name     = each.value
  instance = google_sql_database_instance.main.name
}
resource "google_sql_user" "iam_users" {
  for_each = toset(["api", "auth", "indexer", "dataflow"])
  name     = trimsuffix(google_service_account.services[each.key].email, ".gserviceaccount.com")
  instance = google_sql_database_instance.main.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}
resource "google_bigtable_instance" "raw" {
  name                = "${var.name}-raw"
  deletion_protection = true
  cluster {
    cluster_id   = "${var.name}-raw-a"
    zone         = var.zone
    num_nodes    = 1
    storage_type = "SSD"
  }
  depends_on = [google_project_service.services]
}
resource "google_bigtable_table" "observations" {
  name          = "observations"
  instance_name = google_bigtable_instance.raw.name
  column_family { family = "raw" }
}
resource "google_bigtable_gc_policy" "raw" {
  instance_name = google_bigtable_instance.raw.name
  table         = google_bigtable_table.observations.name
  column_family = "raw"
  max_age { duration = "7776000s" }
}
resource "google_pubsub_topic" "raw" {
  name                       = "rental-observations"
  message_retention_duration = "604800s"
  message_storage_policy { allowed_persistence_regions = [var.region] }
  depends_on = [google_project_service.services]
}
resource "google_pubsub_topic" "dead_letter" {
  name = "rental-observations-dead-letter"
  message_storage_policy { allowed_persistence_regions = [var.region] }
}
resource "google_pubsub_subscription" "dataflow" {
  name                       = "rental-observations-dataflow"
  topic                      = google_pubsub_topic.raw.id
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  enable_message_ordering    = false
  expiration_policy { ttl = "" }
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}
resource "google_pubsub_subscription" "dead_letter" {
  name                       = "rental-observations-review"
  topic                      = google_pubsub_topic.dead_letter.id
  message_retention_duration = "1209600s"
  expiration_policy { ttl = "" }
}
resource "google_pubsub_topic_iam_member" "collector" {
  topic  = google_pubsub_topic.raw.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.services["collector"].email}"
}
resource "google_pubsub_subscription_iam_member" "dataflow" {
  subscription = google_pubsub_subscription.dataflow.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.services["dataflow"].email}"
}
resource "google_pubsub_topic_iam_member" "dead_letter" {
  topic  = google_pubsub_topic.dead_letter.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.services["dataflow"].email}"
}
resource "google_storage_bucket" "dataflow" {
  name                        = "${var.project_id}-${var.name}-dataflow"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  lifecycle_rule {
    condition { age = 14 }
    action { type = "Delete" }
  }
}
resource "google_storage_bucket_iam_member" "dataflow" {
  bucket = google_storage_bucket.dataflow.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.services["dataflow"].email}"
}
resource "google_dataflow_flex_template_job" "stream" {
  provider                = google-beta
  count                   = var.enable_dataflow_job ? 1 : 0
  name                    = "${var.name}-normalize"
  region                  = var.region
  container_spec_gcs_path = var.dataflow_template_gcs_path
  service_account_email   = google_service_account.services["dataflow"].email
  network                 = google_compute_network.main.name
  subnetwork              = google_compute_subnetwork.main.self_link
  ip_configuration        = "WORKER_IP_PRIVATE"
  temp_location           = "gs://${google_storage_bucket.dataflow.name}/tmp"
  staging_location        = "gs://${google_storage_bucket.dataflow.name}/staging"
  max_workers             = 2
  on_delete               = "drain"
  parameters = {
    input_subscription = google_pubsub_subscription.dataflow.id
    dead_letter_topic  = google_pubsub_topic.dead_letter.id
    config_secret      = "${google_secret_manager_secret.config["dataflow"].id}/versions/latest"
  }
  lifecycle {
    precondition {
      condition     = !var.enable_dataflow_job || startswith(var.dataflow_template_gcs_path, "gs://")
      error_message = "Supply an existing Flex Template GCS specification before enabling Dataflow."
    }
  }
  depends_on = [google_project_iam_member.roles, google_storage_bucket_iam_member.dataflow]
}
