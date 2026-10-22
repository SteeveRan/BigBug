/**
 * @file cnpg.tf
 * @description CNPG operator only (issue #55). Base deploys the operator, not
 *              database instances — the Postgres Cluster CR is app-layer
 *              (ADR-0029) and is provisioned by the apps root (I6).
 */

resource "helm_release" "cloudnative_pg" {
  name             = "cloudnative-pg"
  repository       = "https://cloudnative-pg.github.io/charts"
  chart            = "cloudnative-pg"
  version          = "0.29.1" # operator 1.30.1, pinned
  namespace        = "cnpg-system"
  create_namespace = true
}
