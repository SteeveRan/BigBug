import { useState } from 'react'
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
  Tooltip,
} from '@mui/material'
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon } from '@mui/icons-material'
import {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
} from '../../store/api'
import { User } from '../../types'

export function AdminPage() {
  const { data: users = [], isLoading } = useListUsersQuery()
  const [createUser] = useCreateUserMutation()
  const [updateUser] = useUpdateUserMutation()
  const [deleteUser] = useDeleteUserMutation()

  const [createOpen, setCreateOpen] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [form, setForm] = useState({ username: '', email: '', password: '', roles: 'viewer' })
  const [submitting, setSubmitting] = useState(false)

  const handleCreate = async () => {
    setSubmitting(true)
    try {
      await createUser({
        username: form.username,
        email: form.email,
        password: form.password,
        roles: [form.roles],
      }).unwrap()
      setCreateOpen(false)
      setForm({ username: '', email: '', password: '', roles: 'viewer' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (user: User) => {
    await updateUser({ id: user.id, data: { is_active: !user.is_active } })
  }

  const handleDelete = async (id: number) => {
    if (confirm('Delete this user?')) {
      await deleteUser(id)
    }
  }

  const roleColor = (role: string): 'error' | 'warning' | 'default' => {
    if (role === 'admin') return 'error'
    if (role === 'operator') return 'warning'
    return 'default'
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">User Management</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Add User
        </Button>
      </Box>

      {isLoading ? (
        <CircularProgress />
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
                <TableRow key={user.id}>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">{user.username}</Typography>
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
                      <IconButton size="small" color="error" onClick={() => handleDelete(user.id)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography color="text.secondary" py={3}>No users found</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add User</DialogTitle>
        <DialogContent>
          <TextField
            label="Username" fullWidth margin="normal" value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })} required
          />
          <TextField
            label="Email" type="email" fullWidth margin="normal" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} required
          />
          <TextField
            label="Password" type="password" fullWidth margin="normal" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} required
          />
          <TextField
            select label="Role" fullWidth margin="normal" value={form.roles}
            onChange={(e) => setForm({ ...form, roles: e.target.value })}
          >
            <option value="viewer">Viewer</option>
            <option value="operator">Operator</option>
            <option value="admin">Admin</option>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained" onClick={handleCreate}
            disabled={!form.username || !form.email || !form.password || submitting}
          >
            {submitting ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
