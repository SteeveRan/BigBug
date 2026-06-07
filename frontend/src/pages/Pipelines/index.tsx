import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
  ToggleButtonGroup,
  ToggleButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  OpenInNew as OpenInNewIcon,
  Cancel as CancelIcon,
  Replay as ReplayIcon,
  PlayArrow as PlayIcon,
} from '@mui/icons-material';
import {
  useGetPipelineRunsQuery,
  useTriggerPipelineMutation,
  useCancelPipelineMutation,
  useRetryPipelineMutation,
  useGetGitlabInstancesQuery,
} from '../../store/api';
import { PipelineRun, STATUS_FLAG } from '../../types';
import { StatusChip } from '../../components/StatusChip';

const STATUS_FILTERS: { label: string; value: number | undefined }[] = [
  { label: 'All', value: undefined },
  { label: 'Running', value: STATUS_FLAG.IN_PROGRESS },
  { label: 'Success', value: STATUS_FLAG.OK },
  { label: 'Failed', value: STATUS_FLAG.FAILED },
];

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '-';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
}

export function PipelinesPage() {
  const [statusFilter, setStatusFilter] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    gitlab_instance_id: 0,
    gitlab_project_id: '',
    ref: '',
    variables: '',
  });

  const { data, isLoading } = useGetPipelineRunsQuery(
    { page, status: statusFilter },
    { pollingInterval: statusFilter === STATUS_FLAG.IN_PROGRESS ? 5000 : 0 }
  );
  const [triggerPipeline, { isLoading: isTriggering }] = useTriggerPipelineMutation();
  const [cancelPipeline] = useCancelPipelineMutation();
  const [retryPipeline] = useRetryPipelineMutation();
  const { data: instances = [] } = useGetGitlabInstancesQuery();

  const handleTrigger = async () => {
    const variables: Record<string, string> = {};
    if (form.variables.trim()) {
      form.variables.split('\n').forEach((line) => {
        const [key, ...rest] = line.split('=');
        if (key.trim()) {
          variables[key.trim()] = rest.join('=').trim();
        }
      });
    }

    await triggerPipeline({
      gitlab_instance_id: form.gitlab_instance_id,
      gitlab_project_id: parseInt(form.gitlab_project_id, 10),
      ref: form.ref,
      variables,
    }).unwrap();

    setDialogOpen(false);
    setForm({ gitlab_instance_id: 0, gitlab_project_id: '', ref: '', variables: '' });
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
          Pipeline Runs
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <ToggleButtonGroup
            size="small"
            value={statusFilter ?? ''}
            exclusive
            onChange={(_, v) => {
              setStatusFilter(v === '' ? undefined : (v as number));
              setPage(1);
            }}
          >
            {STATUS_FILTERS.map((f) => (
              <ToggleButton key={f.label} value={f.value ?? ''}>
                {f.label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <Button
            variant="contained"
            startIcon={<PlayIcon />}
            onClick={() => setDialogOpen(true)}
          >
            Run Pipeline
          </Button>
        </Box>
      </Box>

      {isLoading ? (
        <CircularProgress />
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>#ID</TableCell>
                <TableCell>Project</TableCell>
                <TableCell>Ref</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Duration</TableCell>
                <TableCell>Created</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.items.map((run: PipelineRun) => (
                <TableRow key={run.id} hover>
                  <TableCell>
                    {run.gitlab_pipeline_id ? `#${run.gitlab_pipeline_id}` : `PR#${run.id}`}
                  </TableCell>
                  <TableCell>{run.gitlab_project_id}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {run.ref}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusChip
                      statusFlag={run.status_flag as typeof STATUS_FLAG[keyof typeof STATUS_FLAG]}
                      statusText={run.status_text}
                    />
                  </TableCell>
                  <TableCell>{formatDuration(run.duration)}</TableCell>
                  <TableCell>{formatDate(run.created_at)}</TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                      {run.web_url && (
                        <Tooltip title="Open in GitLab">
                          <IconButton
                            size="small"
                            href={run.web_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <OpenInNewIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                      {run.status_flag === STATUS_FLAG.IN_PROGRESS && (
                        <Tooltip title="Cancel">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => cancelPipeline(run.id)}
                          >
                            <CancelIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                      {run.status_flag === STATUS_FLAG.FAILED && (
                        <Tooltip title="Retry">
                          <IconButton
                            size="small"
                            color="primary"
                            onClick={() => retryPipeline(run.id)}
                          >
                            <ReplayIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
              {data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Typography color="text.secondary">No pipeline runs found</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Run Pipeline Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Run Pipeline</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>GitLab Instance</InputLabel>
              <Select
                value={form.gitlab_instance_id || ''}
                label="GitLab Instance"
                onChange={(e) =>
                  setForm({ ...form, gitlab_instance_id: e.target.value as number })
                }
              >
                {instances.map((inst) => (
                  <MenuItem key={inst.id} value={inst.id}>
                    {inst.name} ({inst.url})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="GitLab Project ID"
              type="number"
              fullWidth
              value={form.gitlab_project_id}
              onChange={(e) => setForm({ ...form, gitlab_project_id: e.target.value })}
            />
            <TextField
              label="Ref (branch, tag, commit SHA)"
              fullWidth
              value={form.ref}
              onChange={(e) => setForm({ ...form, ref: e.target.value })}
              placeholder="main"
            />
            <TextField
              label="Variables (key=value, one per line)"
              fullWidth
              multiline
              minRows={2}
              maxRows={6}
              value={form.variables}
              onChange={(e) => setForm({ ...form, variables: e.target.value })}
              placeholder="DEPLOY_ENV=staging&#10;VERSION=1.0.0"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleTrigger}
            disabled={
              isTriggering ||
              !form.gitlab_instance_id ||
              !form.gitlab_project_id ||
              !form.ref
            }
          >
            {isTriggering ? <CircularProgress size={20} /> : 'Trigger'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
