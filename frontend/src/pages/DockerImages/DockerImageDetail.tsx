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
  Divider,
  Link,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import { ArrowBack, Refresh, OpenInNew } from '@mui/icons-material';
import { useState } from 'react';
import {
  useGetDockerImageQuery,
  useGetDockerImageTagsQuery,
  useGetDockerImageLogsQuery,
  useIndexDockerImageMutation,
} from '../../store/api';
import { DockerImageSourceDetail, DockerImageTag, DockerSyncLog } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function DockerImageDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const sourceId = Number(id);

  const { data: source, isLoading } = useGetDockerImageQuery(sourceId);
  const { data: tags = [] } = useGetDockerImageTagsQuery(sourceId);
  const { data: logs = [] } = useGetDockerImageLogsQuery(sourceId);
  const [indexImage, { isLoading: indexing }] = useIndexDockerImageMutation();

  const [indexDialogOpen, setIndexDialogOpen] = useState(false);
  const [imageName, setImageName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const s = source as DockerImageSourceDetail | undefined;

  const handleIndex = async () => {
    setSubmitting(true);
    try {
      await indexImage({ id: sourceId, image_name: imageName }).unwrap();
      setIndexDialogOpen(false);
      setImageName('');
    } finally {
      setSubmitting(false);
    }
  };

  const formatBytes = (bytes: number | null): string => {
    if (bytes === null) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIdx = 0;
    while (size >= 1024 && unitIdx < units.length - 1) {
      size /= 1024;
      unitIdx++;
    }
    return `${size.toFixed(1)} ${units[unitIdx]}`;
  };

  if (isLoading) return <CircularProgress />;
  if (!s) return <Typography>Docker image source not found</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/docker-images')}>
          Back
        </Button>
        <Typography variant="h5" fontWeight="bold" sx={{ flexGrow: 1 }}>
          {s.name}
        </Typography>
        <Button
          variant="contained"
          startIcon={<Refresh />}
          onClick={() => setIndexDialogOpen(true)}
          disabled={indexing}
        >
          Index Image
        </Button>
        <Button
          startIcon={<OpenInNew />}
          href={s.registry_url}
          target="_blank"
          rel="noopener noreferrer"
          variant="outlined"
        >
          Open Registry
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Card sx={{ flex: '1 1 300px' }}>
          <CardContent>
            <Typography variant="h6" mb={2}>
              Source Info
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Status
                </Typography>
                <Box mt={0.5}>
                  <StatusChip
                    statusFlag={s.status_flag as 0 | 1 | 2 | 3 | 4}
                    statusText={s.status_text}
                  />
                </Box>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Registry URL
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all' }}
                >
                  {s.registry_url}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body2">{s.description ?? '—'}</Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Last Synced
                </Typography>
                <Typography variant="body2">
                  {s.last_synced_at ? new Date(s.last_synced_at).toLocaleString() : 'Never'}
                </Typography>
              </Box>
              {s.gitlab_project_url && (
                <>
                  <Divider />
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      GitLab Project
                    </Typography>
                    <Typography variant="body2">
                      <Link href={s.gitlab_project_url} target="_blank" rel="noopener noreferrer">
                        {s.gitlab_project_id ?? s.gitlab_project_url}
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
            <Typography variant="h6" mb={2}>
              Image Tags ({tags.length})
            </Typography>
            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Image</TableCell>
                    <TableCell>Tag</TableCell>
                    <TableCell>Architecture</TableCell>
                    <TableCell>Size</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(tags as DockerImageTag[]).map((tag) => (
                    <TableRow key={tag.id}>
                      <TableCell>
                        <Typography
                          variant="body2"
                          fontWeight="medium"
                          sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
                        >
                          {tag.image_name}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {tag.tag}
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {tag.architectures ?? '—'}
                      </TableCell>
                      <TableCell>{formatBytes(tag.size_bytes)}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <StatusChip
                            statusFlag={tag.status_flag as 0 | 1 | 2 | 3 | 4}
                            statusText={tag.status_text}
                          />
                          {tag.is_synced && (
                            <Typography variant="caption" color="success.main" fontWeight="bold">
                              ✓ Synced
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                  {tags.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} align="center">
                        <Typography color="text.secondary" py={2}>
                          No tags indexed yet. Click "Index Image" to fetch tags.
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
                {(logs as DockerSyncLog[]).map((log) => (
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

      {/* Index Image Dialog */}
      <Dialog
        open={indexDialogOpen}
        onClose={() => setIndexDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Index Image Tags</DialogTitle>
        <DialogContent>
          <TextField
            label="Image Name"
            fullWidth
            margin="normal"
            value={imageName}
            onChange={(e) => setImageName(e.target.value)}
            placeholder="library/nginx"
            helperText="Full image name to index (e.g., library/nginx, bitnami/postgresql)"
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIndexDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleIndex} disabled={!imageName || submitting}>
            {submitting ? <CircularProgress size={20} /> : 'Index'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
