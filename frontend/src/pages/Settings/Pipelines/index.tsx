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
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import {
  useGetComponentsQuery,
  useCreateComponentMutation,
  useUpdateComponentMutation,
  useDeleteComponentMutation,
  useGetGitlabInstancesQuery,
} from '../../../store/api';
import { GitLabComponent, GitLabComponentCreate } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';

const emptyForm: GitLabComponentCreate = {
  name: '',
  description: '',
  gitlab_instance_id: 0,
  project_path: '',
  component_path: '',
  version: '',
  inputs_schema: undefined,
};

export function GitLabComponentsPage() {
  const { data: components = [], isLoading } = useGetComponentsQuery();
  const { data: instances = [] } = useGetGitlabInstancesQuery();
  const [createComponent] = useCreateComponentMutation();
  const [updateComponent] = useUpdateComponentMutation();
  const [deleteComponent] = useDeleteComponentMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<GitLabComponentCreate>({ ...emptyForm });
  const [submitting, setSubmitting] = useState(false);

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...emptyForm });
    setDialogOpen(true);
  };

  const openEdit = (component: GitLabComponent) => {
    setEditingId(component.id);
    setForm({
      name: component.name,
      description: component.description ?? '',
      gitlab_instance_id: component.gitlab_instance_id,
      project_path: component.project_path,
      component_path: component.component_path,
      version: component.version ?? '',
      inputs_schema: component.inputs_schema ?? undefined,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    setSubmitting(true);
    try {
      const payload: GitLabComponentCreate = {
        ...form,
        description: form.description || undefined,
        version: form.version || undefined,
      };

      if (editingId) {
        await updateComponent({ id: editingId, data: payload }).unwrap();
      } else {
        await createComponent(payload).unwrap();
      }
      setDialogOpen(false);
      setForm({ ...emptyForm });
      setEditingId(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Delete this component?')) {
      await deleteComponent(id);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
          GitLab Components
        </Typography>
        <PermissionGate permission="pipelines:manage">
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            Add Component
          </Button>
        </PermissionGate>
      </Box>

      {isLoading ? (
        <CircularProgress />
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Project Path</TableCell>
                <TableCell>Component Path</TableCell>
                <TableCell>Version</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {components.map((c: GitLabComponent) => (
                <TableRow key={c.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                      {c.name}
                    </Typography>
                    {c.description && (
                      <Typography variant="caption" color="text.secondary">
                        {c.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {c.project_path}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {c.component_path}
                    </Typography>
                  </TableCell>
                  <TableCell>{c.version || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      label={c.is_enabled ? 'Enabled' : 'Disabled'}
                      color={c.is_enabled ? 'success' : 'default'}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <PermissionGate permission="pipelines:manage">
                      <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                        <Tooltip title="Edit">
                          <IconButton size="small" onClick={() => openEdit(c)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleDelete(c.id)}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </PermissionGate>
                  </TableCell>
                </TableRow>
              ))}
              {components.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary">No components registered</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Add / Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{editingId ? 'Edit Component' : 'Add Component'}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label="Name"
              fullWidth
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              label="Description"
              fullWidth
              multiline
              minRows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
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
                    {inst.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Project Path"
              fullWidth
              value={form.project_path}
              onChange={(e) => setForm({ ...form, project_path: e.target.value })}
              placeholder="my-group/my-project"
            />
            <TextField
              label="Component Path"
              fullWidth
              value={form.component_path}
              onChange={(e) => setForm({ ...form, component_path: e.target.value })}
              placeholder="templates/my-component.yml"
            />
            <TextField
              label="Version"
              fullWidth
              value={form.version}
              onChange={(e) => setForm({ ...form, version: e.target.value })}
              placeholder="1.0.0"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={submitting || !form.name || !form.gitlab_instance_id || !form.project_path || !form.component_path}
          >
            {submitting ? <CircularProgress size={20} /> : editingId ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
