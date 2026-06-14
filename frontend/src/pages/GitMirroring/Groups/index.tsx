/**
 * @file Groups/index.tsx
 * @description Redirect — groups are now part of the unified Sources page.
 *              Redirects to /git-mirroring/sources?tab=groups
 * @dependencies react-router
 */

import { Navigate } from 'react-router';

export function GroupsPage() {
  return <Navigate to="/git-mirroring/sources?tab=groups" replace />;
}

export default GroupsPage;
