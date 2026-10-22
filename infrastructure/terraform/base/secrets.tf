/**
 * @file secrets.tf
 * @description App secrets in k8s (ADR-0024, issue #56). Depends on the CNPG
 *              cluster (the operator's <cluster>-app secret is the credentials
 *              source) and the namespace.
 */

module "k8s_secrets" {
  source = "./modules/k8s-secrets"

  depends_on = [kubernetes_manifest.cnpg_cluster]

  # Literal: must match the Cluster spec in cnpg.tf (manifest attr is
  # unavailable at refresh time — see kubernetes_manifest plan-time limitations).
  cnpg_app_secret_name = "bigbug-dev"
}
