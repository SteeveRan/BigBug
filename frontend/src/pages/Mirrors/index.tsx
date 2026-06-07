import { useState } from 'react';
import { useNavigate } from 'react-router';
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
  Tooltip,
  IconButton,
} from '@mui/material';
import { Add as AddIcon, PlayArrow as SyncIcon } from '@mui/icons-material';
import {
  useListMirrorsQuery,
  useImportMirrorMutation,
  useTriggerSyncMutation,
} from '../../store/api';
import { GitlabMirror } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function MirrorsPage() {
  const navigate = useNavigate();
  const { data: mirrors = [], isLoading } = useListMirrorsQuery();
  const [importMirror] = useImportMirrorMutation();
  const [triggerSync] = useTriggerSyncMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [gitlabUrl, setGitlabUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleImport = async () => {
    setSubmitting(true);
    try {
      await importMirror({ github_url: githubUrl, gitlab_url: gitlabUrl }).unwrap();
      setDialogOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">
          GitLab Mirrors
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setGithubUrl('');
            setGitlabUrl('');
            setDialogOpen(true);
          }}
        >
          Import Mirror
        </Button>
      </Box>

      {isLoading ? (
        <CircularProgress />
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>GitLab Project</TableCell>
                <TableCell>Branch</TableCell>
                <TableCell>Last Sync</TableCell>
                <TableCell>Last Release Tag</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(mirrors as GitlabMirror[]).map((mirror) => (
                <TableRow
                  key={mirror.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/mirrors/${mirror.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {mirror.gitlab_name ?? mirror.gitlab_url}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {mirror.gitlab_namespace}
                    </Typography>
                  </TableCell>
                  <TableCell>{mirror.mirrored_branch}</TableCell>
                  <TableCell>
                    {mirror.last_sync_at ? new Date(mirror.last_sync_at).toLocaleString() : '—'}
                  </TableCell>
                  <TableCell>{mirror.last_synced_release_tag ?? '—'}</TableCell>
                  <TableCell>
                    <StatusChip
                      statusFlag={mirror.status_flag as 0 | 1 | 2 | 3 | 4}
                      statusText={mirror.status_text}
                    />
                  </TableCell>
                  <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                    <Tooltip title="Trigger sync now">
                      <IconButton size="small" onClick={() => triggerSync(mirror.id)}>
                        <SyncIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {mirrors.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" py={3}>
                      No mirrors yet. Import a mirror to get started.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Import Mirror</DialogTitle>
        <DialogContent>
          <TextField
            label="GitHub URL"
            fullWidth
            margin="normal"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            required
          />
          <TextField
            label="GitLab URL"
            fullWidth
            margin="normal"
            value={gitlabUrl}
            onChange={(e) => setGitlabUrl(e.target.value)}
            placeholder="https://gitlab.example.com/namespace/repo"
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleImport}
            disabled={!githubUrl || !gitlabUrl || submitting}
          >
            {submitting ? <CircularProgress size={20} /> : 'Import'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
