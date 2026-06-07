/**
 * @file Admin/index.tsx
 * @description Admin page with two tabs: Users and Roles management.
 *              Roles tab provides full CRUD with 34 permission checkboxes
 *              grouped by resource, builtin-role protection, and delete confirmation.
 * @dependencies @mui/material, @mui/icons-material, ../../store/api, ../../types, ../../components/PermissionGate
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState, useCallback } from 'react';
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
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  FormGroup,
  Checkbox,
  Tooltip,
  Snackbar,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Lock as LockIcon,
} from '@mui/icons-material';

import type { Role, RoleCreate, RoleUpdate } from '../../types';
import {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useGetAllRolesQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
} from '../../store/api';
import { PermissionGate } from '../../components/PermissionGate';
import type { User } from '../../types';

// ─── Permission groups (34 permissions in 9 resource groups) ────────────────

interface PermissionGroup {
  label: string;
  permissions: string[];
}

const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    label: 'Mirrors',
    permissions: ['mirrors:read', 'mirrors:write', 'mirrors:delete', 'mirrors:sync'],
  },
  {
    label: 'Projects',
    permissions: ['projects:read', 'projects:write', 'projects:delete'],
  },
  {
    label: 'Helm',
    permissions: ['helm:read', 'helm:write', 'helm:delete', 'helm:sync'],
  },
  {
    label: 'Docker',
    permissions: ['docker:read', 'docker:write', 'docker:delete', 'docker:sync'],
  },
  {
    label: 'Gold Images',
    permissions: [
      'gold_images:read',
      'gold_images:write',
      'gold_images:delete',
      'gold_images:build',
    ],
  },
  {
    label: 'App Images',
    permissions: [
      'app_images:read',
      'app_images:write',
      'app_images:delete',
      'app_images:build',
    ],
  },
  {
    label: 'Users',
    permissions: ['users:read', 'users:write', 'users:delete'],
  },
  {
    label: 'Roles',
    permissions: ['roles:read', 'roles:write', 'roles:delete'],
  },
  {
    label: 'System',
    permissions: [
      'system:settings',
      'system:audit',
      'system:integrations',
      'system:oidc_config',
      'pipelines:manage',
    ],
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Derive a human-readable label from a permission string like "mirrors:read" */
function permissionLabel(perm: string): string {
  const [resource, action] = perm.split(':');
  if (!action) return perm;
  return `${action} → ${resource}`;
}

// ─── Snackbar state ──────────────────────────────────────────────────────────

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

const EMPTY_SNACKBAR: SnackbarState = { open: false, message: '', severity: 'success' };

// ─── Tab panel helper ────────────────────────────────────────────────────────

function TabPanel({ children, value, index }: { children: React.ReactNode; value: number; index: number }) {
  if (value !== index) return null;
  return <Box sx={{ pt: 3 }}>{children}</Box>;
}

// ─── Users Tab ───────────────────────────────────────────────────────────────

function UsersTab() {
  const { data: users = [], isLoading } = useListUsersQuery();
  const [createUser] = useCreateUserMutation();
  const [updateUser] = useUpdateUserMutation();
  const [deleteUser] = useDeleteUserMutation();

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ username: '', email: '', password: '', roles: 'viewer' });
  const [submitting, setSubmitting] = useState(false);
  const [snackbar, setSnackbar] = useState<SnackbarState>(EMPTY_SNACKBAR);

  const showSnackbar = useCallback((message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  }, []);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createUser({
        username: form.username,
        email: form.email,
        password: form.password,
        roles: [form.roles],
      }).unwrap();
      setCreateOpen(false);
      setForm({ username: '', email: '', password: '', roles: 'viewer' });
      showSnackbar(`User "${form.username}" created successfully`, 'success');
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to create user')
          : 'Failed to create user';
      showSnackbar(message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      await updateUser({ id: user.id, data: { is_active: !user.is_active } }).unwrap();
      showSnackbar(
        `User "${user.username}" ${user.is_active ? 'deactivated' : 'activated'}`,
        'success'
      );
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to update user')
          : 'Failed to update user';
      showSnackbar(message, 'error');
    }
  };

  const handleDelete = async (user: User) => {
    if (!confirm(`Delete user "${user.username}"?`)) return;
    try {
      await deleteUser(user.id).unwrap();
      showSnackbar(`User "${user.username}" deleted`, 'success');
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to delete user')
          : 'Failed to delete user';
      showSnackbar(message, 'error');
    }
  };

  const roleColor = (role: string): 'error' | 'warning' | 'default' => {
    if (role === 'admin') return 'error';
    if (role === 'operator') return 'warning';
    return 'default';
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">User Management</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Add User
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Username</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Roles</TableCell>
                <TableCell>Active</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(users as User[]).map((user) => (
                <TableRow key={user.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                      {user.username}
                    </Typography>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {user.roles.map((role) => (
                        <Chip key={role} label={role} size="small" color={roleColor(role)} />
                      ))}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={user.is_active}
                      onChange={() => handleToggleActive(user)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Delete user">
                      <IconButton size="small" color="error" onClick={() => handleDelete(user)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography color="text.secondary" sx={{ py: 3 }}>
                      No users found
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Create User Dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add User</DialogTitle>
        <DialogContent>
          <TextField
            label="Username"
            fullWidth
            margin="normal"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
          />
          <TextField
            label="Email"
            type="email"
            fullWidth
            margin="normal"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            margin="normal"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
          <TextField
            select
            label="Role"
            fullWidth
            margin="normal"
            value={form.roles}
            onChange={(e) => setForm({ ...form, roles: e.target.value })}
            slotProps={{ select: { native: true } }}
          >
            <option value="viewer">Viewer</option>
            <option value="operator">Operator</option>
            <option value="admin">Admin</option>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!form.username || !form.email || !form.password || submitting}
          >
            {submitting ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar(EMPTY_SNACKBAR)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar(EMPTY_SNACKBAR)}
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

// ─── Roles Tab ───────────────────────────────────────────────────────────────

function RolesTab() {
  const { data: roles = [], isLoading } = useGetAllRolesQuery();
  const [createRole] = useCreateRoleMutation();
  const [updateRole] = useUpdateRoleMutation();
  const [deleteRole] = useDeleteRoleMutation();

  // Snackbar
  const [snackbar, setSnackbar] = useState<SnackbarState>(EMPTY_SNACKBAR);
  const showSnackbar = useCallback((message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  }, []);

  // Create/Edit dialog
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [dialogName, setDialogName] = useState('');
  const [dialogDescription, setDialogDescription] = useState('');
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);

  // Delete confirmation dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingRole, setDeletingRole] = useState<Role | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // ─── Permission selection helpers ─────────────────────────────────────────

  const isGroupAllSelected = useCallback(
    (group: PermissionGroup): boolean => {
      return group.permissions.every((p) => selectedPermissions.includes(p));
    },
    [selectedPermissions]
  );

  const isGroupSomeSelected = useCallback(
    (group: PermissionGroup): boolean => {
      return group.permissions.some((p) => selectedPermissions.includes(p));
    },
    [selectedPermissions]
  );

  const handleToggleGroup = useCallback(
    (group: PermissionGroup, select: boolean) => {
      setSelectedPermissions((prev) => {
        if (select) {
          // Add all group permissions not already selected
          const toAdd = group.permissions.filter((p) => !prev.includes(p));
          return [...prev, ...toAdd];
        }
        // Remove all group permissions
        return prev.filter((p) => !group.permissions.includes(p));
      });
    },
    []
  );

  const handleTogglePermission = useCallback((perm: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm]
    );
  }, []);

  // ─── Dialog handlers ──────────────────────────────────────────────────────

  const handleOpenCreate = () => {
    setEditingRole(null);
    setDialogName('');
    setDialogDescription('');
    setSelectedPermissions([]);
    setDialogOpen(true);
  };

  const handleOpenEdit = (role: Role) => {
    setEditingRole(role);
    setDialogName(role.name);
    setDialogDescription(role.description ?? '');
    setSelectedPermissions(role.permissions.map((p) => p.name));
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingRole(null);
  };

  const handleSaveRole = async () => {
    if (!dialogName.trim()) return;
    setIsSaving(true);
    try {
      if (editingRole) {
        const data: RoleUpdate = {
          name: dialogName.trim() !== editingRole.name ? dialogName.trim() : undefined,
          description:
            dialogDescription.trim() !== (editingRole.description ?? '')
              ? dialogDescription.trim() || null
              : undefined,
          permission_names: selectedPermissions,
        };
        await updateRole({ id: editingRole.id, data }).unwrap();
        showSnackbar(`Role "${dialogName.trim()}" updated successfully`, 'success');
      } else {
        const data: RoleCreate = {
          name: dialogName.trim(),
          description: dialogDescription.trim() || undefined,
          permission_names: selectedPermissions,
        };
        await createRole(data).unwrap();
        showSnackbar(`Role "${dialogName.trim()}" created successfully`, 'success');
      }
      handleCloseDialog();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to save role')
          : 'Failed to save role';
      showSnackbar(message, 'error');
    } finally {
      setIsSaving(false);
    }
  };

  // ─── Delete handlers ──────────────────────────────────────────────────────

  const handleOpenDelete = (role: Role) => {
    setDeletingRole(role);
    setDeleteDialogOpen(true);
  };

  const handleCloseDelete = () => {
    setDeleteDialogOpen(false);
    setDeletingRole(null);
  };

  const handleConfirmDelete = async () => {
    if (!deletingRole) return;
    setIsDeleting(true);
    try {
      await deleteRole(deletingRole.id).unwrap();
      showSnackbar(`Role "${deletingRole.name}" deleted successfully`, 'success');
      handleCloseDelete();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to delete role')
          : 'Failed to delete role';
      showSnackbar(message, 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  // ─── Permission label lookup ──────────────────────────────────────────────

  // ─── Render ───────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Role Management</Typography>
        <PermissionGate permission="roles:write">
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleOpenCreate}>
            Create Role
          </Button>
        </PermissionGate>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Permissions</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(roles as Role[]).map((role) => (
              <TableRow key={role.id} hover>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {!role.is_custom && (
                      <Tooltip title="Built-in role — cannot be modified">
                        <LockIcon fontSize="small" color="action" />
                      </Tooltip>
                    )}
                    <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                      {role.name}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {role.description ?? '—'}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={role.is_custom ? 'Custom' : 'Builtin'}
                    size="small"
                    color={role.is_custom ? 'primary' : 'default'}
                    variant={role.is_custom ? 'filled' : 'outlined'}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={`${role.permissions.length}`}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  <PermissionGate permission="roles:write">
                    <Tooltip title={role.is_custom ? 'Edit role' : 'Built-in roles cannot be edited'}>
                      <span>
                        <IconButton
                          size="small"
                          onClick={() => handleOpenEdit(role)}
                          disabled={!role.is_custom}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  </PermissionGate>
                  <PermissionGate permission="roles:delete">
                    <Tooltip title={role.is_custom ? 'Delete role' : 'Built-in roles cannot be deleted'}>
                      <span>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleOpenDelete(role)}
                          disabled={!role.is_custom}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  </PermissionGate>
                </TableCell>
              </TableRow>
            ))}
            {roles.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography color="text.secondary" sx={{ py: 3 }}>
                    No roles found
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* ─── Create / Edit Role Dialog ─────────────────────────────────────── */}
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {editingRole ? `Edit Role: ${editingRole.name}` : 'Create Role'}
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Name & Description */}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <TextField
                label="Name"
                value={dialogName}
                onChange={(e) => setDialogName(e.target.value)}
                required
                disabled={isSaving}
                sx={{ flex: '1 1 240px' }}
                helperText="Lowercase, alphanumeric with underscores (e.g. dev_lead)"
              />
              <TextField
                label="Description"
                value={dialogDescription}
                onChange={(e) => setDialogDescription(e.target.value)}
                disabled={isSaving}
                sx={{ flex: '2 1 360px' }}
                helperText="Optional. Human-readable description of the role."
              />
            </Box>

            {/* Permissions grouped by resource */}
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Permissions
              </Typography>
              {PERMISSION_GROUPS.map((group) => (
                <Paper
                  key={group.label}
                  variant="outlined"
                  sx={{ p: 1.5, mb: 1.5 }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      mb: 0.5,
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                      {group.label}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => handleToggleGroup(group, true)}
                        disabled={isSaving || isGroupAllSelected(group)}
                        sx={{ minWidth: 'auto', textTransform: 'none' }}
                      >
                        Select All
                      </Button>
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => handleToggleGroup(group, false)}
                        disabled={isSaving || !isGroupSomeSelected(group)}
                        sx={{ minWidth: 'auto', textTransform: 'none' }}
                      >
                        Deselect All
                      </Button>
                    </Box>
                  </Box>
                  <FormGroup row>
                    {group.permissions.map((perm) => (
                      <FormControlLabel
                        key={perm}
                        control={
                          <Checkbox
                            checked={selectedPermissions.includes(perm)}
                            onChange={() => handleTogglePermission(perm)}
                            disabled={isSaving}
                            size="small"
                          />
                        }
                        label={permissionLabel(perm)}
                        sx={{ minWidth: 180 }}
                      />
                    ))}
                  </FormGroup>
                </Paper>
              ))}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveRole}
            disabled={!dialogName.trim() || isSaving}
          >
            {isSaving ? <CircularProgress size={20} /> : editingRole ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Delete Confirmation Dialog ────────────────────────────────────── */}
      <Dialog open={deleteDialogOpen} onClose={handleCloseDelete} maxWidth="xs" fullWidth>
        <DialogTitle>Delete Role</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete role "{deletingRole?.name}"?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDelete} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirmDelete}
            disabled={isDeleting}
          >
            {isDeleting ? <CircularProgress size={20} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Snackbar ──────────────────────────────────────────────────────── */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar(EMPTY_SNACKBAR)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar(EMPTY_SNACKBAR)}
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

// ─── Main AdminPage ──────────────────────────────────────────────────────────

export function AdminPage() {
  const [tabIndex, setTabIndex] = useState(0);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Admin
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
        Manage users, roles, and permissions for the BigBug platform.
      </Typography>

      <Tabs value={tabIndex} onChange={(_, newVal) => setTabIndex(newVal)}>
        <Tab label="Users" />
        <Tab label="Roles" />
      </Tabs>

      <TabPanel value={tabIndex} index={0}>
        <UsersTab />
      </TabPanel>
      <TabPanel value={tabIndex} index={1}>
        <RolesTab />
      </TabPanel>
    </Box>
  );
}

export default AdminPage;
