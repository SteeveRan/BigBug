/**
 * @file backend.tf
 * @description Shared local backend — state lives in ~/.local/state/bigbug/
 *              so every worktree on this machine sees the same state
 *              (multi-agent discipline: infrastructure is common, state must
 *              be common too; ADR-0029 isolated-states pattern preserved via
 *              one path per root).
 */

terraform {
  backend "local" {
    path = pathexpand("~/.local/state/bigbug/base/terraform.tfstate")
  }
}
