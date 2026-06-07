/**
 * @file webhooks.tf
 * @description Project webhooks — HTTP notifications to BigBug backend
 * @resource harbor_project_webhook
 */

resource "harbor_project_webhook" "backend_notifications" {
  name        = "bigbug-backend-webhook"
  project_id  = harbor_project.gold_images.id
  notify_type = "http"
  address     = var.webhook_backend_url
  events_types = [
    "PUSH_ARTIFACT",
    "DELETE_ARTIFACT",
    "SCANNING_COMPLETED",
  ]
  skip_cert_verify = true
}
