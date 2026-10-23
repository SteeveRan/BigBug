/**
 * @file outputs.tf
 * @description Outputs for the BigBug app-infra root.
 */

output "bigbug_namespace" {
  description = "Namespace holding the BigBug app infrastructure"
  value       = module.bigbug_init.namespace
}
