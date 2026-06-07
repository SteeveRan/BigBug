import { useParams, useNavigate } from 'react-router';
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
  Switch,
  FormControlLabel,
  TextField,
  Divider,
} from '@mui/material';
import { ArrowBack, PlayArrow, OpenInNew } from '@mui/icons-material';
import { useState } from 'react';
import {
  useGetMirrorQuery,
  useGetMirrorLogsQuery,
  useGetMirrorScheduleQuery,
  useUpdateMirrorScheduleMutation,
  useTriggerSyncMutation,
} from '../../store/api';
import { GitlabMirror, SyncLog, SyncSchedule } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function MirrorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const mirrorId = Number(id);

  const { data: mirror, isLoading } = useGetMirrorQuery(mirrorId);
  const { data: logs = [] } = useGetMirrorLogsQuery(mirrorId);
  const { data: schedule } = useGetMirrorScheduleQuery(mirrorId);
  const [updateSchedule] = useUpdateMirrorScheduleMutation();
  const [triggerSync, { isLoading: syncing }] = useTriggerSyncMutation();

  const [cronExpr, setCronExpr] = useState('');

  const m = mirror as GitlabMirror | undefined;
  const s = schedule as SyncSchedule | undefined;

  const handleToggleEnabled = async () => {
    if (!s) return;
    await updateSchedule({ id: mirrorId, data: { is_enabled: !s.is_enabled } });
  };

  const handleToggleDefault = async () => {
    if (!s) return;
    await updateSchedule({ id: mirrorId, data: { use_default_schedule: !s.use_default_schedule } });
  };

  const handleSaveCron = async () => {
    await updateSchedule({
      id: mirrorId,
      data: { cron_expression: cronExpr, use_default_schedule: false },
    });
  };

  if (isLoading) return <CircularProgress />;
  if (!m) return <Typography>Mirror not found</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/mirrors')}>
          Back
        </Button>
        <Typography variant="h5" fontWeight="bold" sx={{ flexGrow: 1 }}>
          {m.gitlab_name ?? m.gitlab_url}
        </Typography>
        <Button
          variant="contained"
          startIcon={<PlayArrow />}
          onClick={() => triggerSync(mirrorId)}
          disabled={syncing}
        >
          Sync Now
        </Button>
        <Button
          startIcon={<OpenInNew />}
          href={m.gitlab_url}
          target="_blank"
          rel="noopener noreferrer"
          variant="outlined"
        >
          GitLab
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Card sx={{ flex: '1 1 300px' }}>
          <CardContent>
            <Typography variant="h6" mb={2}>
              Mirror Info
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Status
                </Typography>
                <Box mt={0.5}>
                  <StatusChip
                    statusFlag={m.status_flag as 0 | 1 | 2 | 3 | 4}
                    statusText={m.status_text}
                  />
                </Box>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Branch
                </Typography>
                <Typography variant="body2">{m.mirrored_branch}</Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Last Sync
                </Typography>
                <Typography variant="body2">
                  {m.last_sync_at ? new Date(m.last_sync_at).toLocaleString() : 'Never'}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Last Synced Release
                </Typography>
                <Typography variant="body2">{m.last_synced_release_tag ?? '—'}</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>

        {s && (
          <Card sx={{ flex: '1 1 300px' }}>
            <CardContent>
              <Typography variant="h6" mb={2}>
                Schedule
              </Typography>
              <FormControlLabel
                control={<Switch checked={s.is_enabled} onChange={handleToggleEnabled} />}
                label="Enable scheduled sync"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={s.use_default_schedule}
                    onChange={handleToggleDefault}
                    disabled={!s.is_enabled}
                  />
                }
                label="Use default schedule"
              />
              {!s.use_default_schedule && s.is_enabled && (
                <Box sx={{ mt: 2 }}>
                  <TextField
                    label="Cron Expression"
                    size="small"
                    value={cronExpr || s.cron_expression || ''}
                    onChange={(e) => setCronExpr(e.target.value)}
                    placeholder="0 2 * * *"
                    fullWidth
                  />
                  <Button size="small" sx={{ mt: 1 }} onClick={handleSaveCron}>
                    Save
                  </Button>
                </Box>
              )}
              {s.last_run_at && (
                <Typography variant="caption" color="text.secondary" display="block" mt={2}>
                  Last run: {new Date(s.last_run_at).toLocaleString()}
                </Typography>
              )}
            </CardContent>
          </Card>
        )}
      </Box>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" mb={2}>
            Sync History
          </Typography>
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
                {(logs as SyncLog[]).map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>{new Date(log.created_at).toLocaleString()}</TableCell>
                    <TableCell>{log.triggered_by ?? '—'}</TableCell>
                    <TableCell>
                      {log.pipeline_url ? (
                        <Button size="small" href={log.pipeline_url} target="_blank">
                          #{log.pipeline_id}
                        </Button>
                      ) : (
                        (log.pipeline_id ?? '—')
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusChip
                        statusFlag={log.status_flag as 0 | 1 | 2 | 3 | 4}
                        statusText={log.status_text}
                      />
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
                      <Typography color="text.secondary" py={2}>
                        No sync history yet
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
  );
}
