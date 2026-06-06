import { useState } from 'react'
import { useNavigate } from 'react-router'
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
} from '@mui/material'
import { Add as AddIcon, Refresh as RefreshIcon } from '@mui/icons-material'
import {
  useListDockerImagesQuery,
  useCreateDockerImageMutation,
} from '../../store/api'
import { DockerImageSource } from '../../types'
import { StatusChip } from '../../components/StatusChip'

export function DockerImagesPage() {
  const navigate = useNavigate()
  const { data: sources = [], isLoading } = useListDockerImagesQuery()
  const [createSource] = useCreateDockerImageMutation()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState({
    name: '',
    registry_url: '',
    description: '',
    image_name: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleCreate = async () => {
    setSubmitting(true)
    try {
      await createSource({
        name: form.name,
        registry_url: form.registry_url,
        description: form.description || undefined,
        image_name: form.image_name || undefined,
      }).unwrap()
      setDialogOpen(false)
      setForm({ name: '', registry_url: '', description: '', image_name: '' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">Docker Images</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setForm({ name: '', registry_url: '', description: '', image_name: '' })
            setDialogOpen(true)
          }}
        >
          Add Registry
        </Button>
      </Box>

      {isLoading ? (
        <CircularProgress />
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Registry URL</TableCell>
                <TableCell>Last Synced</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(sources as DockerImageSource[]).map((source) => (
                <TableRow
                  key={source.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/docker-images/${source.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {source.name}
                    </Typography>
                    {source.description && (
                      <Typography variant="caption" color="text.secondary">
                        {source.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                      {source.registry_url}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {source.last_synced_at
                      ? new Date(source.last_synced_at).toLocaleString()
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <StatusChip
                      statusFlag={source.status_flag as 0 | 1 | 2 | 3 | 4}
                      statusText={source.status_text}
                    />
                  </TableCell>
                  <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                    <Tooltip title="Go to details">
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/docker-images/${source.id}`)}
                      >
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {sources.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography color="text.secondary" py={3}>
                      No Docker image sources yet. Add a registry to get started.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Docker Registry</DialogTitle>
        <DialogContent>
          <TextField
            label="Name"
            fullWidth
            margin="normal"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Docker Hub"
            required
          />
          <TextField
            label="Registry URL"
            fullWidth
            margin="normal"
            value={form.registry_url}
            onChange={(e) => setForm({ ...form, registry_url: e.target.value })}
            placeholder="https://registry-1.docker.io"
            required
          />
          <TextField
            label="Image Name (optional)"
            fullWidth
            margin="normal"
            value={form.image_name}
            onChange={(e) => setForm({ ...form, image_name: e.target.value })}
            placeholder="library/nginx"
            helperText="Specific image to index immediately after creation"
          />
          <TextField
            label="Description"
            fullWidth
            margin="normal"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!form.name || !form.registry_url || submitting}
          >
            {submitting ? <CircularProgress size={20} /> : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
