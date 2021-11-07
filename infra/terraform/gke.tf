resource "google_container_cluster" "main" {
  name                     = var.name
  location                 = var.zone
  network                  = google_compute_network.main.id
  subnetwork               = google_compute_subnetwork.main.id
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = true
  networking_mode          = "VPC_NATIVE"
  datapath_provider        = "ADVANCED_DATAPATH"
  release_channel { channel = "REGULAR" }
  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = true
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.admin_cidrs
      content {
        cidr_block   = cidr_blocks.value
        display_name = "operator-${cidr_blocks.key}"
      }
    }
  }
  maintenance_policy {
    recurring_window {
      start_time = "2026-01-04T01:00:00Z"
      end_time   = "2026-01-04T05:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SA,SU"
    }
  }
  logging_config { enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"] }
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus { enabled = true }
  }
  binary_authorization { evaluation_mode = "DISABLED" }
  depends_on = [google_project_service.services]
}
resource "google_container_node_pool" "core" {
  name           = "core"
  cluster        = google_container_cluster.main.name
  location       = var.zone
  node_count     = 1
  node_locations = [var.zone]
  management {
    auto_repair  = true
    auto_upgrade = true
  }
  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
  }
  node_config {
    machine_type    = "e2-standard-4"
    disk_size_gb    = 60
    disk_type       = "pd-balanced"
    service_account = google_service_account.services["nodes"].email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = { workload = "core" }
    workload_metadata_config { mode = "GKE_METADATA" }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
resource "google_container_node_pool" "spot" {
  name               = "collectors-spot"
  cluster            = google_container_cluster.main.name
  location           = var.zone
  initial_node_count = 0
  node_locations     = [var.zone]
  autoscaling {
    min_node_count = 0
    max_node_count = 2
  }
  management {
    auto_repair  = true
    auto_upgrade = true
  }
  node_config {
    spot            = true
    machine_type    = "e2-standard-2"
    disk_size_gb    = 30
    service_account = google_service_account.services["nodes"].email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = { workload = "collectors" }
    taint {
      key    = "workload"
      value  = "collectors"
      effect = "NO_SCHEDULE"
    }
    workload_metadata_config { mode = "GKE_METADATA" }
  }
}
resource "google_gke_hub_membership" "main" {
  membership_id = var.name
  location      = "global"
  endpoint {
    gke_cluster { resource_link = "//container.googleapis.com/${google_container_cluster.main.id}" }
  }
  authority { issuer = "https://container.googleapis.com/v1/${google_container_cluster.main.id}" }
}
