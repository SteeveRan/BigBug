/**
 * @file splitMyProviders.ts
 * @description Чистый client-side helper: делит список провайдеров из
 *              `GET /api/providers` на «owned» (принадлежащие пользователю)
 *              и «shared» (расшаренные на команды пользователя).
 * @dependencies ../../types (ResourceProvider)
 */

import type { ResourceProvider } from '../../types';

export interface SplitMyProvidersResult {
  owned: ResourceProvider[];
  shared: ResourceProvider[];
}

/**
 * Разделяет провайдеры на принадлежащие пользователю и расшаренные на его команды.
 *
 * - `owned`: провайдер, где `owner_user_id === userId` (любая visibility).
 * - `shared`: провайдер с `visibility === 'team'`, у которого `team_id`
 *   входит в `myTeamIds` (только команды, где пользователь реально член;
 *   защищает от админ-«все команды»).
 *
 * @param providers Полный список провайдеров из `useGetProvidersQuery()`.
 * @param userId ID текущего пользователя (может быть `undefined`).
 * @param myTeamIds Множество ID команд, где `my_role !== null`.
 */
export function splitMyProviders(
  providers: ResourceProvider[],
  userId: number | undefined,
  myTeamIds: Set<number>
): SplitMyProvidersResult {
  const owned = providers.filter((p) => userId != null && p.owner_user_id === userId);
  const shared = providers.filter(
    (p) => p.visibility === 'team' && p.team_id != null && myTeamIds.has(p.team_id)
  );
  return { owned, shared };
}
