/**
 * @file memberships.tf
 * @description Group memberships for the BigBug backend service account.
 */

resource "gitlab_group_membership" "backend_mirrors" {
  group_id     = gitlab_group.mirrors.id
  user_id      = gitlab_user.backend.id
  access_level = "maintainer"
}
