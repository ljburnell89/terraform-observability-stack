variable "prometheus_port" {
  description = "Host port to expose Prometheus on"
  type        = number
  default     = 9090
}

variable "alertmanager_port" {
  description = "Host port to expose Alertmanager on"
  type        = number
  default     = 9093
}

variable "grafana_port" {
  description = "Host port to expose Grafana on"
  type        = number
  default     = 3000
}

variable "node_exporter_port" {
  description = "Host port to expose node-exporter metrics on"
  type        = number
  default     = 9100
}

variable "app_port" {
  description = "Host port to expose the demo app on"
  type        = number
  default     = 8000
}

variable "grafana_admin_user" {
  description = "Initial Grafana admin username"
  type        = string
  default     = "admin"
}

variable "grafana_admin_password" {
  description = "Initial Grafana admin password — change this, don't commit a real one to Git"
  type        = string
  default     = "changeme123"
  sensitive   = true
}
