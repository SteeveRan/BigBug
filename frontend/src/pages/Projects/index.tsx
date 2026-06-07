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
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  OpenInNew as OpenIcon,
  Warning as StaleIcon,
} from '@mui/icons-material';
import {
  useListProjectsQuery,
  useCreateProjectMutation,
  useImportProjectMutation,
  useRefreshProjectMutation,
} from '../../store/api';
import { GithubProject } from '../../types';

export function ProjectsPage() {
  const navigate = useNavigate();
  const { data: projects = [], isLoading } = useListProjectsQuery();
  const [createProject] = useCreateProjectMutation();
  const [importProject] = useImportProjectMutation();
  const [refreshProject] = useRefreshProjectMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [gitlabUrl, setGitlabUrl] = useState('');
  const [isImport, setIsImport] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleAdd = () => {
    setIsImport(false);
    setGithubUrl('');
    setGitlabUrl('');
    setDialogOpen(true);
  };

  const handleImport = () => {
    setIsImport(true);
    setGithubUrl('');
    setGitlabUrl('');
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      if (isImport) {
        await importProject({ github_url: githubUrl, gitlab_url: gitlabUrl }).unwrap();
      } else {
        await createProject({ github_url: githubUrl }).unwrap();
      }
      setDialogOpen(false);
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">
          GitHub Projects
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={handleImport}>
            Import Existing
          </Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd}>
            Add Project
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
                <TableCell>Project</TableCell>
                <TableCell>Organization</TableCell>
                <TableCell>License</TableCell>
                <TableCell>Last Synced</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(projects as GithubProject[]).map((project) => (
                <TableRow
                  key={project.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/projects/${project.id}`)}
                >
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" fontWeight="medium">
                        {project.name}
                      </Typography>
                      {project.is_stale && (
                        <Tooltip title="Stale — not synced recently">
                          <StaleIcon color="warning" fontSize="small" />
                        </Tooltip>
                      )}
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {project.full_name}
                    </Typography>
                  </TableCell>
                  <TableCell>{project.org.login}</TableCell>
                  <TableCell>
                    {project.license_spdx ? (
                      <Chip label={project.license_spdx} size="small" />
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {project.last_synced_at
                      ? new Date(project.last_synced_at).toLocaleDateString()
                      : '—'}
                  </TableCell>
                  <TableCell>
                    {project.is_archived && <Chip label="Archived" size="small" color="default" />}
                    {project.is_fork && (
                      <Chip label="Fork" size="small" color="info" sx={{ ml: 0.5 }} />
                    )}
                  </TableCell>
                  <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                    <Tooltip title="Refresh from GitHub">
                      <IconButton size="small" onClick={() => refreshProject(project.id)}>
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Open on GitHub">
                      <IconButton
                        size="small"
                        component="a"
                        href={project.github_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <OpenIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {projects.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" py={3}>
                      No projects yet. Add a GitHub project to get started.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{isImport ? 'Import Existing Mirror' : 'Add GitHub Project'}</DialogTitle>
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
          {isImport && (
            <TextField
              label="GitLab URL"
              fullWidth
              margin="normal"
              value={gitlabUrl}
              onChange={(e) => setGitlabUrl(e.target.value)}
              placeholder="https://gitlab.example.com/namespace/repo"
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSubmit} disabled={!githubUrl || submitting}>
            {submitting ? <CircularProgress size={20} /> : isImport ? 'Import' : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
