/**
 * @file Repositories/index.tsx
 * @description Redirect — repositories are now part of the unified Sources page.
 *              Redirects to /git-mirroring/sources?tab=repositories
 * @dependencies react-router
 */

import { Navigate } from 'react-router';

export function RepositoriesPage() {
  return <Navigate to="/git-mirroring/sources?tab=repositories" replace />;
}

export default RepositoriesPage;
