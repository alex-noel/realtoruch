output "cluster_name" { value = google_container_cluster.main.name }
output "fleet_membership" { value = google_gke_hub_membership.main.name }
output "sql_connection_name" { value = google_sql_database_instance.main.connection_name }
output "sql_private_ip" { value = google_sql_database_instance.main.private_ip_address }
output "service_accounts" { value = { for name, account in google_service_account.services : name => account.email } }
output "configuration_secrets" { value = { for name, secret in google_secret_manager_secret.config : name => secret.id } }
output "web_bucket" { value = google_storage_bucket.web.name }
output "web_ip" { value = google_compute_global_address.web.address }
output "api_ip" { value = google_compute_global_address.api.address }
output "images" { value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}" }
output "dataflow_staging_bucket" { value = google_storage_bucket.dataflow.name }
