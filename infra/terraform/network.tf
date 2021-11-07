locals {
  services = toset([
    "compute.googleapis.com", "container.googleapis.com", "gkehub.googleapis.com",
    "sqladmin.googleapis.com", "servicenetworking.googleapis.com", "pubsub.googleapis.com",
    "dataflow.googleapis.com", "bigtable.googleapis.com", "bigtableadmin.googleapis.com",
    "secretmanager.googleapis.com", "artifactregistry.googleapis.com", "monitoring.googleapis.com",
    "logging.googleapis.com", "storage.googleapis.com", "iam.googleapis.com"
  ])
}
resource "google_project_service" "services" {
  for_each           = local.services
  service            = each.value
  disable_on_destroy = false
}
resource "google_compute_network" "main" {
  name                    = var.name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.services]
}
resource "google_compute_subnetwork" "main" {
  name                     = "${var.name}-private"
  network                  = google_compute_network.main.id
  region                   = var.region
  ip_cidr_range            = "10.40.0.0/20"
  private_ip_google_access = true
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.44.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.48.0.0/20"
  }
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.1
    metadata             = "EXCLUDE_ALL_METADATA"
  }
}
resource "google_compute_router" "main" {
  name    = var.name
  network = google_compute_network.main.id
}
resource "google_compute_router_nat" "egress" {
  name                               = "${var.name}-egress"
  router                             = google_compute_router.main.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
resource "google_compute_global_address" "service_range" {
  name          = "${var.name}-managed-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}
resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.service_range.name]
}
resource "google_compute_firewall" "dataflow_internal" {
  name        = "${var.name}-dataflow-workers"
  network     = google_compute_network.main.name
  source_tags = ["dataflow"]
  target_tags = ["dataflow"]
  allow {
    protocol = "tcp"
    ports    = ["12345", "12346"]
  }
}
