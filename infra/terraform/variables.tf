variable "project_id" {
  description = "Existing GCP project. This configuration never creates a project."
  type        = string
}
variable "region" {
  type    = string
  default = "europe-central2"
}
variable "zone" {
  type    = string
  default = "europe-central2-a"
}
variable "name" {
  type    = string
  default = "realtoruch"
}
variable "admin_cidrs" {
  description = "VPN or operator CIDRs allowed to reach the private GKE control plane."
  type        = list(string)
  default     = ["10.40.0.0/20"]
}
variable "cdn_domain" {
  description = "Domain for the static web app. DNS must be configured separately."
  type        = string
}
variable "api_domain" {
  description = "API hostname used by uptime monitoring and the Helm ingress."
  type        = string
}
variable "alert_emails" {
  type    = list(string)
  default = []
}
variable "dataflow_template_gcs_path" {
  description = "Existing gs:// Flex Template spec. Empty keeps the job unprovisioned."
  type        = string
  default     = ""
}
variable "enable_dataflow_job" {
  description = "Enable only after a tested worker image and template have been published."
  type        = bool
  default     = false
}
variable "enable_uptime_monitoring" {
  type    = bool
  default = false
}
