/**
 * @file valkey.tf
 * @description Valkey — single-node cache for the app (ADR-0022: без operator
 *              в dev). Ephemeral storage (no PV) — cache data loss is
 *              acceptable on dev.
 *              Consumers connect to: valkey.bigbug.svc:6379 (no auth in dev)
 */

resource "kubernetes_deployment_v1" "valkey" {
  depends_on = [kubernetes_namespace.bigbug]

  metadata {
    name      = "valkey"
    namespace = "bigbug"
    labels    = { app = "valkey" }
  }

  spec {
    replicas = 1
    selector {
      match_labels = { app = "valkey" }
    }
    template {
      metadata {
        labels = { app = "valkey" }
      }
      spec {
        container {
          name  = "valkey"
          image = "valkey/valkey:8.1.10"
          port {
            container_port = 6379
          }
          readiness_probe {
            tcp_socket {
              port = 6379
            }
          }
          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              memory = "128Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "valkey" {
  metadata {
    name      = "valkey"
    namespace = "bigbug"
  }
  spec {
    selector = {
      app = "valkey"
    }
    port {
      port        = 6379
      target_port = 6379
    }
  }
}
