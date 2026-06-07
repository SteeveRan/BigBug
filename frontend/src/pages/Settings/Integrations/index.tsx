/**
 * @file Settings/Integrations/index.tsx
 * @description Settings page for managing integration instances (GitLab, Harbor, GitHub, Docker Registry, Helm Repository).
 *              Uses MUI Tabs, Tables, Dialogs for CRUD operations and connection testing.
 * @dependencies @mui/material, @mui/icons-material, ../../store/api, ../../components/StatusChip
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState, useCallback } from 'react';
import {
  Box,
  Tabs,
  Tab,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
  CircularProgress,
  Alert,
  Snackbar,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as TestIcon,
} from '@mui/icons-material';
import { StatusChip } from '../../../components/StatusChip';
import type {
  GitlabInstance,
  GitlabInstanceCreate,
  GitlabInstanceUpdate,
  HarborInstance,
  HarborInstanceCreate,
  HarborInstanceUpdate,
  GithubInstance,
  GithubInstanceCreate,
  GithubInstanceUpdate,
  DockerRegistryInstance,
  DockerRegistryInstanceCreate,
  DockerRegistryInstanceUpdate,
  HelmRepositoryInstance,
  HelmRepositoryInstanceCreate,
  HelmRepositoryInstanceUpdate,
  ConnectionTestResult,
  StatusFlag,
} from '../../../types';
import {
  useGetGitlabInstancesQuery,
  useCreateGitlabInstanceMutation,
  useUpdateGitlabInstanceMutation,
  useDeleteGitlabInstanceMutation,
  useTestGitlabConnectionMutation,
  useGetHarborInstancesQuery,
  useCreateHarborInstanceMutation,
  useUpdateHarborInstanceMutation,
  useDeleteHarborInstanceMutation,
  useTestHarborConnectionMutation,
  useGetGithubInstancesQuery,
  useCreateGithubInstanceMutation,
  useUpdateGithubInstanceMutation,
  useDeleteGithubInstanceMutation,
  useTestGithubConnectionMutation,
  useGetDockerRegistryInstancesQuery,
  useCreateDockerRegistryInstanceMutation,
  useUpdateDockerRegistryInstanceMutation,
  useDeleteDockerRegistryInstanceMutation,
  useTestDockerRegistryConnectionMutation,
  useGetHelmRepositoryInstancesQuery,
  useCreateHelmRepositoryInstanceMutation,
  useUpdateHelmRepositoryInstanceMutation,
  useDeleteHelmRepositoryInstanceMutation,
  useTestHelmRepositoryConnectionMutation,
} from '../../../store/api';

// ─── Constants ───────────────────────────────────────────────────────────────

const TAB_LABELS = ['GitLab', 'Harbor', 'GitHub', 'Docker Registry', 'Helm Repository'] as const;

// ─── Dialog state ────────────────────────────────────────────────────────────

interface DialogState {
  open: boolean;
  mode: 'add' | 'edit';
  instanceId?: number;
  defaultValues?: Record<string, unknown>;
}

const EMPTY_DIALOG: DialogState = { open: false, mode: 'add' };

// ─── Snackbar state ──────────────────────────────────────────────────────────

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

const EMPTY_SNACKBAR: SnackbarState = { open: false, message: '', severity: 'success' };

// ─── Form validation helpers ─────────────────────────────────────────────────

function isValidUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

interface FormErrors {
  name?: string;
  url?: string;
  username?: string;
  token?: string;
  password?: string;
}

// ─── Main component ──────────────────────────────────────────────────────────

export function SettingsIntegrations() {
  const [tabIndex, setTabIndex] = useState(0);
  const [snackbar, setSnackbar] = useState<SnackbarState>(EMPTY_SNACKBAR);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabIndex(newValue);
  };

  const showSnackbar = useCallback((message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  }, []);

  const hideSnackbar = useCallback(() => {
    setSnackbar(EMPTY_SNACKBAR);
  }, []);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={tabIndex} onChange={handleTabChange} aria-label="Integration type tabs">
          {TAB_LABELS.map((label) => (
            <Tab key={label} label={label} />
          ))}
        </Tabs>
      </Box>

      {tabIndex === 0 && <GitlabPanel showSnackbar={showSnackbar} />}
      {tabIndex === 1 && <HarborPanel showSnackbar={showSnackbar} />}
      {tabIndex === 2 && <GithubPanel showSnackbar={showSnackbar} />}
      {tabIndex === 3 && <DockerRegistryPanel showSnackbar={showSnackbar} />}
      {tabIndex === 4 && <HelmRepositoryPanel showSnackbar={showSnackbar} />}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={hideSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={hideSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}

// ─── Panel props ─────────────────────────────────────────────────────────────

interface PanelProps {
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// GitLab Panel
// ═══════════════════════════════════════════════════════════════════════════════

function GitlabPanel({ showSnackbar }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetGitlabInstancesQuery();
  const [createInstance] = useCreateGitlabInstanceMutation();
  const [updateInstance] = useUpdateGitlabInstanceMutation();
  const [deleteInstance] = useDeleteGitlabInstanceMutation();
  const [testConnection] = useTestGitlabConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: GitlabInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        url: instance.url,
        token: '',
        is_active: instance.is_active,
        verify_ssl: instance.verify_ssl,
        is_default: instance.is_default,
        default_group_id: instance.default_group_id ?? '',
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete GitLab instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showSnackbar(`GitLab instance "${name}" deleted`, 'success');
    } catch {
      showSnackbar('Failed to delete GitLab instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showSnackbar(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error'
      );
    } catch {
      showSnackbar('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">GitLab Instances</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd}>
          Add Instance
        </Button>
      </Box>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load GitLab instances. Please try again later.
        </Alert>
      )}

      {instances && (
        <TableContainer component={Paper}>
          <Table aria-label="GitLab instances table">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>URL</TableCell>
                <TableCell>Default</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {instances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography color="text.secondary" sx={{ py: 2 }}>
                      No GitLab instances configured
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                instances.map((inst) => (
                  <TableRow key={inst.id} hover>
                    <TableCell>{inst.name}</TableCell>
                    <TableCell>{inst.url}</TableCell>
                    <TableCell>{inst.is_default ? 'Yes' : 'No'}</TableCell>
                    <TableCell>
                      <StatusChip
                        statusFlag={inst.status_flag as StatusFlag}
                        statusText={inst.status_text}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleEdit(inst)}
                          aria-label={`Edit ${inst.name}`}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(inst.id, inst.name)}
                          aria-label={`Delete ${inst.name}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Test Connection">
                        <IconButton
                          size="small"
                          onClick={() => handleTest(inst.id)}
                          disabled={testLoading === inst.id}
                          aria-label={`Test connection to ${inst.name}`}
                        >
                          {testLoading === inst.id ? (
                            <CircularProgress size={18} />
                          ) : (
                            <TestIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {dialog.open && (
        <GitlabDialog
          open={dialog}
          onClose={handleClose}
          createInstance={createInstance}
          updateInstance={updateInstance}
          showSnackbar={showSnackbar}
        />
      )}
    </Box>
  );
}

// ─── GitLab Dialog ────────────────────────────────────────────────────────────

interface GitlabDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateGitlabInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateGitlabInstanceMutation>[0];
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

function GitlabDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showSnackbar,
}: GitlabDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [token, setToken] = useState((dialogState.defaultValues?.token as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
  );
  const [defaultGroupId, setDefaultGroupId] = useState(
    (dialogState.defaultValues?.default_group_id as string) ?? ''
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEdit = dialogState.mode === 'edit';

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!url.trim()) {
      newErrors.url = 'URL is required';
    } else if (!isValidUrl(url.trim())) {
      newErrors.url = 'Invalid URL format (must start with http:// or https://)';
    }

    if (!isEdit && !token.trim()) {
      newErrors.token = 'Token is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: GitlabInstanceCreate | GitlabInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        token: token.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
        default_group_id: defaultGroupId.trim() ? Number(defaultGroupId) : null,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as GitlabInstanceUpdate,
        }).unwrap();
        showSnackbar('GitLab instance updated', 'success');
      } else {
        await createInstance(payload as GitlabInstanceCreate).unwrap();
        showSnackbar('GitLab instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={dialogState.open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Edit GitLab Instance' : 'Add GitLab Instance'}</DialogTitle>
      <DialogContent>
        {apiError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {apiError}
          </Alert>
        )}
        <TextField
          label="Name"
          fullWidth
          margin="normal"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={!!errors.name}
          helperText={errors.name}
          required
          autoFocus
        />
        <TextField
          label="URL"
          fullWidth
          margin="normal"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          error={!!errors.url}
          helperText={errors.url ?? 'e.g. https://gitlab.example.com'}
          required
          placeholder="https://gitlab.example.com"
        />
        <TextField
          label={isEdit ? 'Token (leave blank to keep current)' : 'Token'}
          fullWidth
          margin="normal"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          error={!!errors.token}
          helperText={errors.token}
          type="password"
          required={!isEdit}
        />
        <TextField
          label="Default Group ID"
          fullWidth
          margin="normal"
          value={defaultGroupId}
          onChange={(e) => setDefaultGroupId(e.target.value)}
          type="number"
        />
        <FormControlLabel
          control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
          label="Active"
        />
        <FormControlLabel
          control={
            <Checkbox checked={verifySsl} onChange={(e) => setVerifySsl(e.target.checked)} />
          }
          label="Verify SSL"
        />
        <FormControlLabel
          control={
            <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          }
          label="Default"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
          {submitting ? <CircularProgress size={24} /> : isEdit ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Harbor Panel
// ═══════════════════════════════════════════════════════════════════════════════

function HarborPanel({ showSnackbar }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetHarborInstancesQuery();
  const [createInstance] = useCreateHarborInstanceMutation();
  const [updateInstance] = useUpdateHarborInstanceMutation();
  const [deleteInstance] = useDeleteHarborInstanceMutation();
  const [testConnection] = useTestHarborConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: HarborInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        url: instance.url,
        username: instance.username,
        password: '',
        is_active: instance.is_active,
        verify_ssl: instance.verify_ssl,
        is_default: instance.is_default,
        default_project: instance.default_project ?? '',
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete Harbor instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showSnackbar(`Harbor instance "${name}" deleted`, 'success');
    } catch {
      showSnackbar('Failed to delete Harbor instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showSnackbar(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error'
      );
    } catch {
      showSnackbar('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">Harbor Instances</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd}>
          Add Instance
        </Button>
      </Box>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load Harbor instances. Please try again later.
        </Alert>
      )}

      {instances && (
        <TableContainer component={Paper}>
          <Table aria-label="Harbor instances table">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>URL</TableCell>
                <TableCell>Username</TableCell>
                <TableCell>Default</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {instances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" sx={{ py: 2 }}>
                      No Harbor instances configured
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                instances.map((inst) => (
                  <TableRow key={inst.id} hover>
                    <TableCell>{inst.name}</TableCell>
                    <TableCell>{inst.url}</TableCell>
                    <TableCell>{inst.username}</TableCell>
                    <TableCell>{inst.is_default ? 'Yes' : 'No'}</TableCell>
                    <TableCell>
                      <StatusChip
                        statusFlag={inst.status_flag as StatusFlag}
                        statusText={inst.status_text}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleEdit(inst)}
                          aria-label={`Edit ${inst.name}`}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(inst.id, inst.name)}
                          aria-label={`Delete ${inst.name}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Test Connection">
                        <IconButton
                          size="small"
                          onClick={() => handleTest(inst.id)}
                          disabled={testLoading === inst.id}
                          aria-label={`Test connection to ${inst.name}`}
                        >
                          {testLoading === inst.id ? (
                            <CircularProgress size={18} />
                          ) : (
                            <TestIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {dialog.open && (
        <HarborDialog
          open={dialog}
          onClose={handleClose}
          createInstance={createInstance}
          updateInstance={updateInstance}
          showSnackbar={showSnackbar}
        />
      )}
    </Box>
  );
}

// ─── Harbor Dialog ────────────────────────────────────────────────────────────

interface HarborDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateHarborInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateHarborInstanceMutation>[0];
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

function HarborDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showSnackbar,
}: HarborDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [username, setUsername] = useState((dialogState.defaultValues?.username as string) ?? '');
  const [password, setPassword] = useState((dialogState.defaultValues?.password as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
  );
  const [defaultProject, setDefaultProject] = useState(
    (dialogState.defaultValues?.default_project as string) ?? ''
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEdit = dialogState.mode === 'edit';

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!url.trim()) {
      newErrors.url = 'URL is required';
    } else if (!isValidUrl(url.trim())) {
      newErrors.url = 'Invalid URL format (must start with http:// or https://)';
    }

    if (!username.trim()) {
      newErrors.username = 'Username is required';
    }

    if (!isEdit && !password.trim()) {
      newErrors.password = 'Password is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: HarborInstanceCreate | HarborInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
        default_project: defaultProject.trim() || null,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as HarborInstanceUpdate,
        }).unwrap();
        showSnackbar('Harbor instance updated', 'success');
      } else {
        await createInstance(payload as HarborInstanceCreate).unwrap();
        showSnackbar('Harbor instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={dialogState.open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Edit Harbor Instance' : 'Add Harbor Instance'}</DialogTitle>
      <DialogContent>
        {apiError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {apiError}
          </Alert>
        )}
        <TextField
          label="Name"
          fullWidth
          margin="normal"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={!!errors.name}
          helperText={errors.name}
          required
          autoFocus
        />
        <TextField
          label="URL"
          fullWidth
          margin="normal"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          error={!!errors.url}
          helperText={errors.url ?? 'e.g. https://harbor.example.com'}
          required
          placeholder="https://harbor.example.com"
        />
        <TextField
          label="Username"
          fullWidth
          margin="normal"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          error={!!errors.username}
          helperText={errors.username}
          required
        />
        <TextField
          label={isEdit ? 'Password (leave blank to keep current)' : 'Password'}
          fullWidth
          margin="normal"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={!!errors.password}
          helperText={errors.password}
          type="password"
          required={!isEdit}
        />
        <TextField
          label="Default Project"
          fullWidth
          margin="normal"
          value={defaultProject}
          onChange={(e) => setDefaultProject(e.target.value)}
        />
        <FormControlLabel
          control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
          label="Active"
        />
        <FormControlLabel
          control={
            <Checkbox checked={verifySsl} onChange={(e) => setVerifySsl(e.target.checked)} />
          }
          label="Verify SSL"
        />
        <FormControlLabel
          control={
            <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          }
          label="Default"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
          {submitting ? <CircularProgress size={24} /> : isEdit ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// GitHub Panel
// ═══════════════════════════════════════════════════════════════════════════════

function GithubPanel({ showSnackbar }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetGithubInstancesQuery();
  const [createInstance] = useCreateGithubInstanceMutation();
  const [updateInstance] = useUpdateGithubInstanceMutation();
  const [deleteInstance] = useDeleteGithubInstanceMutation();
  const [testConnection] = useTestGithubConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: GithubInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        token: '',
        is_active: instance.is_active,
        is_default: instance.is_default,
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete GitHub instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showSnackbar(`GitHub instance "${name}" deleted`, 'success');
    } catch {
      showSnackbar('Failed to delete GitHub instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showSnackbar(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error'
      );
    } catch {
      showSnackbar('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">GitHub Instances</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd}>
          Add Instance
        </Button>
      </Box>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load GitHub instances. Please try again later.
        </Alert>
      )}

      {instances && (
        <TableContainer component={Paper}>
          <Table aria-label="GitHub instances table">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Default</TableCell>
                <TableCell>Last Checked</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {instances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography color="text.secondary" sx={{ py: 2 }}>
                      No GitHub instances configured
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                instances.map((inst) => (
                  <TableRow key={inst.id} hover>
                    <TableCell>{inst.name}</TableCell>
                    <TableCell>{inst.is_default ? 'Yes' : 'No'}</TableCell>
                    <TableCell>
                      {inst.last_checked_at
                        ? new Date(inst.last_checked_at).toLocaleString()
                        : 'Never'}
                    </TableCell>
                    <TableCell>
                      <StatusChip
                        statusFlag={inst.status_flag as StatusFlag}
                        statusText={inst.status_text}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleEdit(inst)}
                          aria-label={`Edit ${inst.name}`}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(inst.id, inst.name)}
                          aria-label={`Delete ${inst.name}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Test Connection">
                        <IconButton
                          size="small"
                          onClick={() => handleTest(inst.id)}
                          disabled={testLoading === inst.id}
                          aria-label={`Test connection to ${inst.name}`}
                        >
                          {testLoading === inst.id ? (
                            <CircularProgress size={18} />
                          ) : (
                            <TestIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {dialog.open && (
        <GithubDialog
          open={dialog}
          onClose={handleClose}
          createInstance={createInstance}
          updateInstance={updateInstance}
          showSnackbar={showSnackbar}
        />
      )}
    </Box>
  );
}

// ─── GitHub Dialog ────────────────────────────────────────────────────────────

interface GithubDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateGithubInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateGithubInstanceMutation>[0];
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

function GithubDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showSnackbar,
}: GithubDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [token, setToken] = useState((dialogState.defaultValues?.token as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEdit = dialogState.mode === 'edit';

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!isEdit && !token.trim()) {
      newErrors.token = 'Token is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: GithubInstanceCreate | GithubInstanceUpdate = {
        name: name.trim(),
        token: token.trim() || undefined,
        is_active: isActive,
        is_default: isDefault,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as GithubInstanceUpdate,
        }).unwrap();
        showSnackbar('GitHub instance updated', 'success');
      } else {
        await createInstance(payload as GithubInstanceCreate).unwrap();
        showSnackbar('GitHub instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={dialogState.open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Edit GitHub Instance' : 'Add GitHub Instance'}</DialogTitle>
      <DialogContent>
        {apiError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {apiError}
          </Alert>
        )}
        <TextField
          label="Name"
          fullWidth
          margin="normal"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={!!errors.name}
          helperText={errors.name}
          required
          autoFocus
        />
        <TextField
          label={isEdit ? 'Token (leave blank to keep current)' : 'Token'}
          fullWidth
          margin="normal"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          error={!!errors.token}
          helperText={errors.token ?? 'Personal Access Token (classic or fine-grained)'}
          type="password"
          required={!isEdit}
        />
        <FormControlLabel
          control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
          label="Active"
        />
        <FormControlLabel
          control={
            <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          }
          label="Default"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
          {submitting ? <CircularProgress size={24} /> : isEdit ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Docker Registry Panel
// ═══════════════════════════════════════════════════════════════════════════════

function DockerRegistryPanel({ showSnackbar }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetDockerRegistryInstancesQuery();
  const [createInstance] = useCreateDockerRegistryInstanceMutation();
  const [updateInstance] = useUpdateDockerRegistryInstanceMutation();
  const [deleteInstance] = useDeleteDockerRegistryInstanceMutation();
  const [testConnection] = useTestDockerRegistryConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: DockerRegistryInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        url: instance.url,
        username: instance.username,
        password: '',
        is_active: instance.is_active,
        verify_ssl: instance.verify_ssl,
        is_default: instance.is_default,
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete Docker Registry instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showSnackbar(`Docker Registry instance "${name}" deleted`, 'success');
    } catch {
      showSnackbar('Failed to delete Docker Registry instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showSnackbar(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error'
      );
    } catch {
      showSnackbar('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">Docker Registry Instances</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd}>
          Add Instance
        </Button>
      </Box>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load Docker Registry instances. Please try again later.
        </Alert>
      )}

      {instances && (
        <TableContainer component={Paper}>
          <Table aria-label="Docker Registry instances table">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>URL</TableCell>
                <TableCell>Username</TableCell>
                <TableCell>Default</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {instances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" sx={{ py: 2 }}>
                      No Docker Registry instances configured
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                instances.map((inst) => (
                  <TableRow key={inst.id} hover>
                    <TableCell>{inst.name}</TableCell>
                    <TableCell>{inst.url}</TableCell>
                    <TableCell>{inst.username}</TableCell>
                    <TableCell>{inst.is_default ? 'Yes' : 'No'}</TableCell>
                    <TableCell>
                      <StatusChip
                        statusFlag={inst.status_flag as StatusFlag}
                        statusText={inst.status_text}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleEdit(inst)}
                          aria-label={`Edit ${inst.name}`}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(inst.id, inst.name)}
                          aria-label={`Delete ${inst.name}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Test Connection">
                        <IconButton
                          size="small"
                          onClick={() => handleTest(inst.id)}
                          disabled={testLoading === inst.id}
                          aria-label={`Test connection to ${inst.name}`}
                        >
                          {testLoading === inst.id ? (
                            <CircularProgress size={18} />
                          ) : (
                            <TestIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {dialog.open && (
        <DockerRegistryDialog
          open={dialog}
          onClose={handleClose}
          createInstance={createInstance}
          updateInstance={updateInstance}
          showSnackbar={showSnackbar}
        />
      )}
    </Box>
  );
}

// ─── Docker Registry Dialog ────────────────────────────────────────────────────

interface DockerRegistryDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateDockerRegistryInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateDockerRegistryInstanceMutation>[0];
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

function DockerRegistryDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showSnackbar,
}: DockerRegistryDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [username, setUsername] = useState((dialogState.defaultValues?.username as string) ?? '');
  const [password, setPassword] = useState((dialogState.defaultValues?.password as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEdit = dialogState.mode === 'edit';

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!url.trim()) {
      newErrors.url = 'URL is required';
    } else if (!isValidUrl(url.trim())) {
      newErrors.url = 'Invalid URL format (must start with http:// or https://)';
    }

    if (!username.trim()) {
      newErrors.username = 'Username is required';
    }

    if (!isEdit && !password.trim()) {
      newErrors.password = 'Password is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: DockerRegistryInstanceCreate | DockerRegistryInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as DockerRegistryInstanceUpdate,
        }).unwrap();
        showSnackbar('Docker Registry instance updated', 'success');
      } else {
        await createInstance(payload as DockerRegistryInstanceCreate).unwrap();
        showSnackbar('Docker Registry instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={dialogState.open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {isEdit ? 'Edit Docker Registry Instance' : 'Add Docker Registry Instance'}
      </DialogTitle>
      <DialogContent>
        {apiError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {apiError}
          </Alert>
        )}
        <TextField
          label="Name"
          fullWidth
          margin="normal"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={!!errors.name}
          helperText={errors.name}
          required
          autoFocus
        />
        <TextField
          label="URL"
          fullWidth
          margin="normal"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          error={!!errors.url}
          helperText={errors.url ?? 'e.g. https://registry.example.com'}
          required
          placeholder="https://registry.example.com"
        />
        <TextField
          label="Username"
          fullWidth
          margin="normal"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          error={!!errors.username}
          helperText={errors.username}
          required
        />
        <TextField
          label={isEdit ? 'Password (leave blank to keep current)' : 'Password'}
          fullWidth
          margin="normal"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={!!errors.password}
          helperText={errors.password}
          type="password"
          required={!isEdit}
        />
        <FormControlLabel
          control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
          label="Active"
        />
        <FormControlLabel
          control={
            <Checkbox checked={verifySsl} onChange={(e) => setVerifySsl(e.target.checked)} />
          }
          label="Verify SSL"
        />
        <FormControlLabel
          control={
            <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          }
          label="Default"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
          {submitting ? <CircularProgress size={24} /> : isEdit ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Helm Repository Panel
// ═══════════════════════════════════════════════════════════════════════════════

function HelmRepositoryPanel({ showSnackbar }: PanelProps) {
  const { data: instances, isLoading, isError } = useGetHelmRepositoryInstancesQuery();
  const [createInstance] = useCreateHelmRepositoryInstanceMutation();
  const [updateInstance] = useUpdateHelmRepositoryInstanceMutation();
  const [deleteInstance] = useDeleteHelmRepositoryInstanceMutation();
  const [testConnection] = useTestHelmRepositoryConnectionMutation();

  const [dialog, setDialog] = useState<DialogState>(EMPTY_DIALOG);
  const [testLoading, setTestLoading] = useState<number | null>(null);

  const handleAdd = () => setDialog({ open: true, mode: 'add' });
  const handleEdit = (instance: HelmRepositoryInstance) => {
    setDialog({
      open: true,
      mode: 'edit',
      instanceId: instance.id,
      defaultValues: {
        name: instance.name,
        url: instance.url,
        username: instance.username,
        password: '',
        is_active: instance.is_active,
        verify_ssl: instance.verify_ssl,
        is_default: instance.is_default,
      },
    });
  };
  const handleClose = () => setDialog(EMPTY_DIALOG);

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete Helm Repository instance "${name}"?`)) return;
    try {
      await deleteInstance(id).unwrap();
      showSnackbar(`Helm Repository instance "${name}" deleted`, 'success');
    } catch {
      showSnackbar('Failed to delete Helm Repository instance', 'error');
    }
  };

  const handleTest = async (id: number) => {
    setTestLoading(id);
    try {
      const result: ConnectionTestResult = await testConnection(id).unwrap();
      showSnackbar(
        result.success ? 'Connection successful' : `Connection failed: ${result.message}`,
        result.success ? 'success' : 'error'
      );
    } catch {
      showSnackbar('Connection test failed', 'error');
    } finally {
      setTestLoading(null);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">Helm Repository Instances</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAdd}>
          Add Instance
        </Button>
      </Box>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load Helm Repository instances. Please try again later.
        </Alert>
      )}

      {instances && (
        <TableContainer component={Paper}>
          <Table aria-label="Helm Repository instances table">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>URL</TableCell>
                <TableCell>Username</TableCell>
                <TableCell>Default</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {instances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" sx={{ py: 2 }}>
                      No Helm Repository instances configured
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                instances.map((inst) => (
                  <TableRow key={inst.id} hover>
                    <TableCell>{inst.name}</TableCell>
                    <TableCell>{inst.url}</TableCell>
                    <TableCell>{inst.username}</TableCell>
                    <TableCell>{inst.is_default ? 'Yes' : 'No'}</TableCell>
                    <TableCell>
                      <StatusChip
                        statusFlag={inst.status_flag as StatusFlag}
                        statusText={inst.status_text}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleEdit(inst)}
                          aria-label={`Edit ${inst.name}`}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(inst.id, inst.name)}
                          aria-label={`Delete ${inst.name}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Test Connection">
                        <IconButton
                          size="small"
                          onClick={() => handleTest(inst.id)}
                          disabled={testLoading === inst.id}
                          aria-label={`Test connection to ${inst.name}`}
                        >
                          {testLoading === inst.id ? (
                            <CircularProgress size={18} />
                          ) : (
                            <TestIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {dialog.open && (
        <HelmRepositoryDialog
          open={dialog}
          onClose={handleClose}
          createInstance={createInstance}
          updateInstance={updateInstance}
          showSnackbar={showSnackbar}
        />
      )}
    </Box>
  );
}

// ─── Helm Repository Dialog ────────────────────────────────────────────────────

interface HelmRepositoryDialogProps {
  open: DialogState;
  onClose: () => void;
  createInstance: ReturnType<typeof useCreateHelmRepositoryInstanceMutation>[0];
  updateInstance: ReturnType<typeof useUpdateHelmRepositoryInstanceMutation>[0];
  showSnackbar: (message: string, severity: 'success' | 'error') => void;
}

function HelmRepositoryDialog({
  open: dialogState,
  onClose,
  createInstance,
  updateInstance,
  showSnackbar,
}: HelmRepositoryDialogProps) {
  const [name, setName] = useState((dialogState.defaultValues?.name as string) ?? '');
  const [url, setUrl] = useState((dialogState.defaultValues?.url as string) ?? '');
  const [username, setUsername] = useState((dialogState.defaultValues?.username as string) ?? '');
  const [password, setPassword] = useState((dialogState.defaultValues?.password as string) ?? '');
  const [isActive, setIsActive] = useState(
    (dialogState.defaultValues?.is_active as boolean) ?? true
  );
  const [verifySsl, setVerifySsl] = useState(
    (dialogState.defaultValues?.verify_ssl as boolean) ?? true
  );
  const [isDefault, setIsDefault] = useState(
    (dialogState.defaultValues?.is_default as boolean) ?? false
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEdit = dialogState.mode === 'edit';

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!url.trim()) {
      newErrors.url = 'URL is required';
    } else if (!isValidUrl(url.trim())) {
      newErrors.url = 'Invalid URL format (must start with http:// or https://)';
    }

    if (!username.trim()) {
      newErrors.username = 'Username is required';
    }

    if (!isEdit && !password.trim()) {
      newErrors.password = 'Password is required for new instances';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    setApiError(null);

    try {
      const payload: HelmRepositoryInstanceCreate | HelmRepositoryInstanceUpdate = {
        name: name.trim(),
        url: url.trim(),
        username: username.trim(),
        password: password.trim() || undefined,
        is_active: isActive,
        verify_ssl: verifySsl,
        is_default: isDefault,
      };

      if (isEdit && dialogState.instanceId) {
        await updateInstance({
          id: dialogState.instanceId,
          data: payload as HelmRepositoryInstanceUpdate,
        }).unwrap();
        showSnackbar('Helm Repository instance updated', 'success');
      } else {
        await createInstance(payload as HelmRepositoryInstanceCreate).unwrap();
        showSnackbar('Helm Repository instance created', 'success');
      }
      onClose();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Operation failed')
          : 'Operation failed';
      setApiError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={dialogState.open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {isEdit ? 'Edit Helm Repository Instance' : 'Add Helm Repository Instance'}
      </DialogTitle>
      <DialogContent>
        {apiError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {apiError}
          </Alert>
        )}
        <TextField
          label="Name"
          fullWidth
          margin="normal"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={!!errors.name}
          helperText={errors.name}
          required
          autoFocus
        />
        <TextField
          label="URL"
          fullWidth
          margin="normal"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          error={!!errors.url}
          helperText={errors.url ?? 'e.g. https://charts.example.com'}
          required
          placeholder="https://charts.example.com"
        />
        <TextField
          label="Username"
          fullWidth
          margin="normal"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          error={!!errors.username}
          helperText={errors.username}
          required
        />
        <TextField
          label={isEdit ? 'Password (leave blank to keep current)' : 'Password'}
          fullWidth
          margin="normal"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={!!errors.password}
          helperText={errors.password}
          type="password"
          required={!isEdit}
        />
        <FormControlLabel
          control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
          label="Active"
        />
        <FormControlLabel
          control={
            <Checkbox checked={verifySsl} onChange={(e) => setVerifySsl(e.target.checked)} />
          }
          label="Verify SSL"
        />
        <FormControlLabel
          control={
            <Checkbox checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          }
          label="Default"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
          {submitting ? <CircularProgress size={24} /> : isEdit ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default SettingsIntegrations;
