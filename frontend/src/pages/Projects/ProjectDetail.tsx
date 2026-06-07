import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  CircularProgress,
  Grid,
  TextField,
  Divider,
} from '@mui/material';
import { ArrowBack, Refresh, OpenInNew } from '@mui/icons-material';
import {
  useGetProjectQuery,
  useUpdateProjectMutation,
  useRefreshProjectMutation,
} from '../../store/api';
import { GithubProject } from '../../types';

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = Number(id);

  const { data: project, isLoading } = useGetProjectQuery(projectId);
  const [updateProject] = useUpdateProjectMutation();
  const [refreshProject, { isLoading: refreshing }] = useRefreshProjectMutation();

  const [editDesc, setEditDesc] = useState(false);
  const [customDesc, setCustomDesc] = useState('');

  const p = project as GithubProject | undefined;

  const handleEditDesc = () => {
    setCustomDesc(p?.custom_description ?? p?.description ?? '');
    setEditDesc(true);
  };

  const handleSaveDesc = async () => {
    await updateProject({ id: projectId, data: { custom_description: customDesc } });
    setEditDesc(false);
  };

  if (isLoading) return <CircularProgress />;
  if (!p) return <Typography>Project not found</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/projects')}>
          Back
        </Button>
        <Typography variant="h5" fontWeight="bold" sx={{ flexGrow: 1 }}>
          {p.full_name}
        </Typography>
        <Button
          startIcon={<Refresh />}
          onClick={() => refreshProject(projectId)}
          disabled={refreshing}
          variant="outlined"
        >
          Refresh from GitHub
        </Button>
        <Button
          startIcon={<OpenInNew />}
          href={p.github_url}
          target="_blank"
          rel="noopener noreferrer"
          variant="outlined"
        >
          GitHub
        </Button>
      </Box>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  mb: 2,
                }}
              >
                <Typography variant="h6">Description</Typography>
                {!editDesc && (
                  <Button size="small" onClick={handleEditDesc}>
                    Edit
                  </Button>
                )}
              </Box>
              {editDesc ? (
                <Box>
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    value={customDesc}
                    onChange={(e) => setCustomDesc(e.target.value)}
                    label="Custom Description"
                  />
                  <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                    <Button variant="contained" size="small" onClick={handleSaveDesc}>
                      Save
                    </Button>
                    <Button size="small" onClick={() => setEditDesc(false)}>
                      Cancel
                    </Button>
                  </Box>
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  {p.custom_description ?? p.description ?? 'No description'}
                </Typography>
              )}
            </CardContent>
          </Card>

          {p.readme_md && (
            <Card>
              <CardContent>
                <Typography variant="h6" mb={2}>
                  README
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    maxHeight: 400,
                    overflow: 'auto',
                    bgcolor: 'grey.50',
                    p: 2,
                    borderRadius: 1,
                  }}
                >
                  {p.readme_md}
                </Box>
              </CardContent>
            </Card>
          )}
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" mb={2}>
                Details
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Organization
                  </Typography>
                  <Typography variant="body2">{p.org.login}</Typography>
                </Box>
                <Divider />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Default Branch
                  </Typography>
                  <Typography variant="body2">{p.default_branch}</Typography>
                </Box>
                <Divider />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    License
                  </Typography>
                  <Typography variant="body2">{p.license_name ?? p.license_spdx ?? '—'}</Typography>
                </Box>
                <Divider />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Last Synced
                  </Typography>
                  <Typography variant="body2">
                    {p.last_synced_at ? new Date(p.last_synced_at).toLocaleString() : 'Never'}
                  </Typography>
                </Box>
                <Divider />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    GitHub Updated
                  </Typography>
                  <Typography variant="body2">
                    {p.github_updated_at ? new Date(p.github_updated_at).toLocaleString() : '—'}
                  </Typography>
                </Box>
                <Divider />
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {p.is_stale && <Chip label="Stale" color="warning" size="small" />}
                  {p.is_archived && <Chip label="Archived" size="small" />}
                  {p.is_fork && <Chip label="Fork" color="info" size="small" />}
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
