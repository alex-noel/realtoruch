locals {
  identities = toset(["nodes", "api", "auth", "search", "collector", "indexer", "dataflow"])
  roles = {
    nodes     = ["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/artifactregistry.reader"]
    api       = ["roles/cloudsql.client", "roles/cloudsql.instanceUser"]
    auth      = ["roles/cloudsql.client", "roles/cloudsql.instanceUser"]
    search    = []
    collector = ["roles/bigtable.user"]
    indexer   = ["roles/cloudsql.client", "roles/cloudsql.instanceUser"]
    dataflow  = ["roles/dataflow.worker", "roles/cloudsql.client", "roles/cloudsql.instanceUser", "roles/artifactregistry.reader"]
  }
  role_bindings = merge([for identity, roles in local.roles : {
    for role in roles : "${identity}-${replace(role, "/", "-")}" => { identity = identity, role = role }
  }]...)
}
resource "google_service_account" "services" {
  for_each     = local.identities
  account_id   = "${var.name}-${each.key}"
  display_name = "${var.name} ${each.key}"
  depends_on   = [google_project_service.services]
}
resource "google_project_iam_member" "roles" {
  for_each = local.role_bindings
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.services[each.value.identity].email}"
}
resource "google_service_account_iam_member" "workload_identity" {
  for_each           = toset(["api", "auth", "search", "collector", "indexer"])
  service_account_id = google_service_account.services[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[realtoruch/${each.key}]"
  depends_on         = [google_container_cluster.main]
}
resource "google_secret_manager_secret" "config" {
  for_each  = toset(["api", "auth", "search", "collector", "indexer", "dataflow"])
  secret_id = "${var.name}-${each.key}-config"
  replication {
    user_managed {
      replicas { location = var.region }
    }
  }
  depends_on = [google_project_service.services]
}
resource "google_secret_manager_secret_iam_member" "config" {
  for_each  = google_secret_manager_secret.config
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.services[each.key].email}"
}
resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = var.name
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}
