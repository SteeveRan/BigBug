/**
 * @file redis.tf
 * @description redis-operator (ot-container-kit, issue #56 session decision:
 *              replaces the bare Valkey deployment). Base deploys the operator
 *              only — the Redis CR (cache instance for the app) is app-layer
 *              and is provisioned by the apps root (I6).
 */

resource "helm_release" "redis_operator" {
  name             = "redis-operator"
  repository       = "https://ot-container-kit.github.io/helm-charts"
  chart            = "redis-operator"
  version          = "0.27.0" # latest chart; Renovate bumps
  namespace        = "redis-operator"
  create_namespace = true

  values = [file("${path.module}/values/redis-operator.yaml")]
}
