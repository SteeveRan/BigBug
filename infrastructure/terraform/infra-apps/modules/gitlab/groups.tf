/**
 * @file groups.tf
 * @description GitLab groups for organizing mirrors.
 */

resource "gitlab_group" "mirrors" {
  name             = var.mirrors_group_name
  path             = var.mirrors_group_name
  description      = "BigBug mirrored repositories"
  visibility_level = "private"

  # Allow merging only through MRs (fully protected)
  default_branch_protection_defaults {
    allowed_to_push  = ["no one"]
    allowed_to_merge = ["developer"]
    allow_force_push = false
  }
}
