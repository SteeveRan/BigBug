import { Grid, Card, CardContent, Typography, Box, CircularProgress } from '@mui/material'
import {
  GitHub as GitHubIcon,
  SwapHoriz as MirrorIcon,
  Layers as GoldImageIcon,
  Apps as AppImageIcon,
} from '@mui/icons-material'
import { useListProjectsQuery, useListMirrorsQuery, useListGoldImagesQuery, useListAppImagesQuery } from '../../store/api'
import { StatusChip } from '../../components/StatusChip'
import { GitlabMirror, STATUS_FLAG } from '../../types'

function StatCard({
  title,
  count,
  icon,
  isLoading,
}: {
  title: string
  count: number
  icon: React.ReactNode
  isLoading: boolean
}) {
  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {title}
            </Typography>
            <Typography variant="h4" fontWeight="bold">
              {isLoading ? <CircularProgress size={28} /> : count}
            </Typography>
          </Box>
          <Box sx={{ color: 'primary.main', opacity: 0.7 }}>{icon}</Box>
        </Box>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { data: projects = [], isLoading: loadingProjects } = useListProjectsQuery()
  const { data: mirrors = [], isLoading: loadingMirrors } = useListMirrorsQuery()
  const { data: goldImages = [], isLoading: loadingGold } = useListGoldImagesQuery()
  const { data: appImages = [], isLoading: loadingApp } = useListAppImagesQuery()

  const staleMirrors = (mirrors as GitlabMirror[]).filter(
    (m) => m.status_flag === STATUS_FLAG.WARNING
  )
  const failedMirrors = (mirrors as GitlabMirror[]).filter(
    (m) => m.status_flag === STATUS_FLAG.FAILED
  )

  return (
    <Box>
      <Typography variant="h5" fontWeight="bold" mb={3}>
        Dashboard
      </Typography>

      <Grid container spacing={3} mb={4}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="GitHub Projects"
            count={projects.length}
            icon={<GitHubIcon sx={{ fontSize: 40 }} />}
            isLoading={loadingProjects}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="GitLab Mirrors"
            count={mirrors.length}
            icon={<MirrorIcon sx={{ fontSize: 40 }} />}
            isLoading={loadingMirrors}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Gold Images"
            count={goldImages.length}
            icon={<GoldImageIcon sx={{ fontSize: 40 }} />}
            isLoading={loadingGold}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="App Images"
            count={appImages.length}
            icon={<AppImageIcon sx={{ fontSize: 40 }} />}
            isLoading={loadingApp}
          />
        </Grid>
      </Grid>

      {(staleMirrors.length > 0 || failedMirrors.length > 0) && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" mb={2}>
              Attention Required
            </Typography>
            {failedMirrors.length > 0 && (
              <Box mb={1}>
                <Typography variant="body2" color="error">
                  {failedMirrors.length} mirror(s) failed last sync
                </Typography>
              </Box>
            )}
            {staleMirrors.length > 0 && (
              <Box>
                <Typography variant="body2" color="warning.main">
                  {staleMirrors.length} mirror(s) are stale
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent>
          <Typography variant="h6" mb={2}>
            Recent Mirrors Status
          </Typography>
          {loadingMirrors ? (
            <CircularProgress />
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {(mirrors as GitlabMirror[]).slice(0, 5).map((mirror) => (
                <Box
                  key={mirror.id}
                  sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                >
                  <Typography variant="body2">{mirror.gitlab_name ?? mirror.gitlab_url}</Typography>
                  <StatusChip statusFlag={mirror.status_flag} statusText={mirror.status_text} />
                </Box>
              ))}
              {mirrors.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No mirrors configured yet
                </Typography>
              )}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  )
}
