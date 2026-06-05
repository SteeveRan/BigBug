/**
 * @file groups.tf
 * @description GitLab groups for organizing mirrors.
 */

resource "gitlab_group" "mirrors" {
  name             = var.mirrors_group_name
  path             = var.mirrors_group_name
  description      = "BigBug mirrored repositories"
  visibility_level = "private"

  # Allow merging only through MRs
  default_branch_protection = 2
}
