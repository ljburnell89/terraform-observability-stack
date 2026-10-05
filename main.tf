terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

# ---------------------------------------------------------------------------
# Network — everything needs to talk to everything else, so put it all on
# one user-defined bridge network rather than relying on Docker's default.
# ---------------------------------------------------------------------------
resource "docker_network" "observability" {
  name = "observability-net"
}

# ---------------------------------------------------------------------------
# Volumes — Grafana needs persistent storage so dashboards survive restarts.
# Prometheus gets one too so metric history isn't lost on recreation.
# ---------------------------------------------------------------------------
resource "docker_volume" "grafana_data" {
  name = "grafana-data"
}

resource "docker_volume" "prometheus_data" {
  name = "prometheus-data"
}

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------
resource "docker_image" "prometheus" {
  name = "prom/prometheus:latest"
}

resource "docker_container" "prometheus" {
  image = docker_image.prometheus.image_id
  name  = "prometheus"

  networks_advanced {
    name = docker_network.observability.name
  }

  ports {
    internal = 9090
    external = var.prometheus_port
  }

  volumes {
    volume_name    = docker_volume.prometheus_data.name
    container_path = "/prometheus"
  }

  volumes {
    host_path      = "${abspath(path.module)}/config/prometheus.yml"
    container_path = "/etc/prometheus/prometheus.yml"
    read_only      = true
  }

  volumes {
    host_path      = "${abspath(path.module)}/config/alert.rules.yml"
    container_path = "/etc/prometheus/alert.rules.yml"
    read_only      = true
  }

  command = [
    "--config.file=/etc/prometheus/prometheus.yml",
    "--storage.tsdb.path=/prometheus",
    "--web.enable-lifecycle",   # lets us reload config without recreating the container
    "--web.cors.origin=.*"      # allows the control panel (a different origin/port) to call Prometheus's API directly from the browser
  ]

  depends_on = [docker_container.app]
}

# ---------------------------------------------------------------------------
# Alertmanager
# ---------------------------------------------------------------------------
resource "docker_image" "alertmanager" {
  name = "prom/alertmanager:latest"
}

resource "docker_container" "alertmanager" {
  image = docker_image.alertmanager.image_id
  name  = "alertmanager"

  networks_advanced {
    name = docker_network.observability.name
  }

  ports {
    internal = 9093
    external = var.alertmanager_port
  }

  volumes {
    host_path      = "${abspath(path.module)}/config/alertmanager.yml"
    container_path = "/etc/alertmanager/alertmanager.yml"
    read_only      = true
  }

  command = [
    "--config.file=/etc/alertmanager/alertmanager.yml"
  ]
}

# ---------------------------------------------------------------------------
# Grafana
# ---------------------------------------------------------------------------
resource "docker_image" "grafana" {
  name = "grafana/grafana:latest"
}

resource "docker_container" "grafana" {
  image = docker_image.grafana.image_id
  name  = "grafana"

  networks_advanced {
    name = docker_network.observability.name
  }

  ports {
    internal = 3000
    external = var.grafana_port
  }

  volumes {
    volume_name    = docker_volume.grafana_data.name
    container_path = "/var/lib/grafana"
  }

  # Auto-provision the Prometheus data source — no manual click-ops needed.
  volumes {
    host_path      = "${abspath(path.module)}/config/grafana/datasources"
    container_path = "/etc/grafana/provisioning/datasources"
    read_only      = true
  }

  # Auto-provision the dashboard definition + tell Grafana where to load it from.
  volumes {
    host_path      = "${abspath(path.module)}/config/grafana/dashboards/dashboard.yml"
    container_path = "/etc/grafana/provisioning/dashboards/dashboard.yml"
    read_only      = true
  }

  volumes {
    host_path      = "${abspath(path.module)}/config/grafana/dashboards/json"
    container_path = "/etc/grafana/provisioning/dashboards/json"
    read_only      = true
  }

  env = [
    "GF_SECURITY_ADMIN_USER=${var.grafana_admin_user}",
    "GF_SECURITY_ADMIN_PASSWORD=${var.grafana_admin_password}",
    "GF_INSTALL_PLUGINS=",
    # Lets the control panel embed a live Grafana panel in an <iframe>
    # (Grafana blocks iframe embedding by default via X-Frame-Options).
    "GF_SECURITY_ALLOW_EMBEDDING=true",
    # Lets the embedded panel render without prompting for a Grafana login —
    # read-only Viewer access only, scoped to this local demo.
    "GF_AUTH_ANONYMOUS_ENABLED=true",
    "GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer"
  ]

  depends_on = [docker_container.prometheus]
}

# ---------------------------------------------------------------------------
# Demo app — built from the local Dockerfile in ./app. This is the
# deliberately-breakable app Prometheus scrapes and Alertmanager fires on.
# ---------------------------------------------------------------------------
resource "docker_image" "app" {
  # Built manually via `docker build -t observability-demo-app:latest ./app`
  # (the provider's own build step is flaky on Windows — see README).
  name         = "observability-demo-app:latest"
  keep_locally = true
}

resource "docker_container" "app" {
  image = "observability-demo-app:latest"
  name  = "app" # must match the target in config/prometheus.yml

  networks_advanced {
    name = docker_network.observability.name
  }

  ports {
    internal = 8000
    external = var.app_port
  }
}

# ---------------------------------------------------------------------------
# Node Exporter — gives you real host-level metrics (CPU, memory, disk) to
# build dashboards and alerts against, beyond just the app itself.
# ---------------------------------------------------------------------------
resource "docker_image" "node_exporter" {
  name = "prom/node-exporter:latest"
}

resource "docker_container" "node_exporter" {
  image = docker_image.node_exporter.image_id
  name  = "node-exporter"

  networks_advanced {
    name = docker_network.observability.name
  }

  ports {
    internal = 9100
    external = var.node_exporter_port
  }
}
