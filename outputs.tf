output "prometheus_url" {
  description = "URL to access the Prometheus UI"
  value       = "http://localhost:${var.prometheus_port}"
}

output "alertmanager_url" {
  description = "URL to access the Alertmanager UI"
  value       = "http://localhost:${var.alertmanager_port}"
}

output "grafana_url" {
  description = "URL to access the Grafana UI"
  value       = "http://localhost:${var.grafana_port}"
}

output "grafana_login" {
  description = "Grafana login hint (password not shown — see variables.tf)"
  value       = "username: ${var.grafana_admin_user}"
}
