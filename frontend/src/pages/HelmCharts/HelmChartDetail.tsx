import { useParams, useNavigate } from 'react-router'
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Divider,
  Link,
} from '@mui/material'
import { ArrowBack, Refresh, OpenInNew } from '@mui/icons-material'
import {
  useGetHelmChartQuery,
  useGetHelmChartVersionsQuery,
  useGetHelmChartLogsQuery,
  useIndexHelmChartMutation,
} from '../../store/api'
import { HelmChartSourceDetail, HelmChartVersion, HelmSyncLog } from '../../types'
import { StatusChip } from '../../components/StatusChip'

export function HelmChartDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const chartId = Number(id)

  const { data: chart, isLoading } = useGetHelmChartQuery(chartId)
  const { data: versions = [] } = useGetHelmChartVersionsQuery(chartId)
  const { data: logs = [] } = useGetHelmChartLogsQuery(chartId)
  const [indexChart, { isLoading: indexing }] = useIndexHelmChartMutation()

  const c = chart as HelmChartSourceDetail | undefined

  if (isLoading) return <CircularProgress />
  if (!c) return <Typography>Helm chart source not found</Typography>

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/helm-charts')}>Back</Button>
        <Typography variant="h5" fontWeight="bold" sx={{ flexGrow: 1 }}>
          {c.name}
        </Typography>
        <Button
          variant="contained"
          startIcon={<Refresh />}
          onClick={() => indexChart(chartId)}
          disabled={indexing}
        >
          Re-index
        </Button>
        <Button
          startIcon={<OpenInNew />}
          href={c.repo_url}
          target="_blank"
          rel="noopener noreferrer"
          variant="outlined"
        >
          Open Repo
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Card sx={{ flex: '1 1 300px' }}>
          <CardContent>
            <Typography variant="h6" mb={2}>Source Info</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">Status</Typography>
                <Box mt={0.5}>
                  <StatusChip statusFlag={c.status_flag as 0|1|2|3|4} statusText={c.status_text} />
                </Box>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">Repository URL</Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all' }}>
                  {c.repo_url}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">Description</Typography>
                <Typography variant="body2">{c.description ?? '—'}</Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">Last Synced</Typography>
                <Typography variant="body2">
                  {c.last_synced_at ? new Date(c.last_synced_at).toLocaleString() : 'Never'}
                </Typography>
              </Box>
              {c.gitlab_project_url && (
                <>
                  <Divider />
                  <Box>
                    <Typography variant="caption" color="text.secondary">GitLab Project</Typography>
                    <Typography variant="body2">
                      <Link href={c.gitlab_project_url} target="_blank" rel="noopener noreferrer">
                        {c.gitlab_project_id ?? c.gitlab_project_url}
                      </Link>
                    </Typography>
                  </Box>
                </>
              )}
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ flex: '2 1 500px' }}>
          <CardContent>
            <Typography variant="h6" mb={2}>Chart Versions ({versions.length})</Typography>
            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Chart</TableCell>
                    <TableCell>Version</TableCell>
                    <TableCell>App Version</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(versions as HelmChartVersion[]).map((v) => (
                    <TableRow key={v.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {v.chart_name}
                        </Typography>
                        {v.description && (
                          <Typography variant="caption" color="text.secondary">
                            {v.description.length > 80 ? v.description.slice(0, 80) + '…' : v.description}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {v.version}
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {v.app_version ?? '—'}
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <StatusChip statusFlag={v.status_flag as 0|1|2|3|4} statusText={v.status_text} />
                          {v.is_synced && (
                            <Typography variant="caption" color="success.main" fontWeight="bold">
                              ✓ Synced
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                  {versions.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} align="center">
                        <Typography color="text.secondary" py={2}>
                          No versions indexed yet. Click "Re-index" to fetch chart versions.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      </Box>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" mb={2}>Sync History</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Triggered By</TableCell>
                  <TableCell>Pipeline</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Duration</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(logs as HelmSyncLog[]).map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>{new Date(log.created_at).toLocaleString()}</TableCell>
                    <TableCell>{log.triggered_by ?? '—'}</TableCell>
                    <TableCell>
                      {log.pipeline_url ? (
                        <Button size="small" href={log.pipeline_url} target="_blank">
                          #{log.pipeline_id}
                        </Button>
                      ) : (
                        log.pipeline_id ?? '—'
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusChip statusFlag={log.status_flag as 0|1|2|3|4} statusText={log.status_text} />
                    </TableCell>
                    <TableCell>
                      {log.started_at && log.finished_at
                        ? `${Math.round((new Date(log.finished_at).getTime() - new Date(log.started_at).getTime()) / 1000)}s`
                        : '—'}
                    </TableCell>
                  </TableRow>
                ))}
                {logs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} align="center">
                      <Typography color="text.secondary" py={2}>No sync history yet</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  )
}
