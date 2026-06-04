import { useState } from 'react'
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  Grid,
  Chip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from '@mui/material'
import { Add as AddIcon, Build as BuildIcon } from '@mui/icons-material'
import {
  useListAppImagesQuery,
  useCreateAppImageMutation,
  useTriggerAppBuildMutation,
  useListGoldImagesQuery,
} from '../../store/api'
import { AppImage, GoldImage } from '../../types'

export function AppImagesPage() {
  const { data: images = [], isLoading } = useListAppImagesQuery()
  const { data: goldImages = [] } = useListGoldImagesQuery()
  const [createImage] = useCreateAppImageMutation()
  const [triggerBuild] = useTriggerAppBuildMutation()

  const [createOpen, setCreateOpen] = useState(false)
  const [buildOpen, setBuildOpen] = useState<number | null>(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
    dockerfile: '',
    gold_image_id: '',
  })
  const [buildForm, setBuildForm] = useState({ version_tag: 'latest', arch: 'amd64' })
  const [submitting, setSubmitting] = useState(false)

  const handleCreate = async () => {
    setSubmitting(true)
    try {
      await createImage({
        ...form,
        gold_image_id: form.gold_image_id ? Number(form.gold_image_id) : undefined,
      }).unwrap()
      setCreateOpen(false)
      setForm({ name: '', description: '', dockerfile: '', gold_image_id: '' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleBuild = async () => {
    if (buildOpen === null) return
    setSubmitting(true)
    try {
      await triggerBuild({ id: buildOpen, ...buildForm }).unwrap()
      setBuildOpen(null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">App Images</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          New App Image
        </Button>
      </Box>

      {isLoading ? (
        <CircularProgress />
      ) : (
        <Grid container spacing={3}>
          {(images as AppImage[]).map((image) => {
            const goldImage = (goldImages as GoldImage[]).find((g) => g.id === image.gold_image_id)
            return (
              <Grid key={image.id} size={{ xs: 12, sm: 6, md: 4 }}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" mb={1}>{image.name}</Typography>
                    {goldImage && (
                      <Chip
                        label={`Base: ${goldImage.name}`}
                        size="small"
                        color="secondary"
                        variant="outlined"
                        sx={{ mb: 1 }}
                      />
                    )}
                    <Typography variant="body2" color="text.secondary" mb={2}>
                      {image.description ?? 'No description'}
                    </Typography>
                    {image.dockerfile && (
                      <Box
                        component="pre"
                        sx={{
                          fontSize: '0.7rem',
                          bgcolor: 'grey.100',
                          p: 1,
                          borderRadius: 1,
                          maxHeight: 80,
                          overflow: 'hidden',
                          fontFamily: 'monospace',
                        }}
                      >
                        {image.dockerfile.slice(0, 200)}
                      </Box>
                    )}
                  </CardContent>
                  <CardActions>
                    <Button
                      size="small"
                      startIcon={<BuildIcon />}
                      onClick={() => {
                        setBuildForm({ version_tag: 'latest', arch: 'amd64' })
                        setBuildOpen(image.id)
                      }}
                    >
                      Build
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            )
          })}
          {images.length === 0 && (
            <Grid size={12}>
              <Typography color="text.secondary" textAlign="center" py={4}>
                No app images yet. Create one to get started.
              </Typography>
            </Grid>
          )}
        </Grid>
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New App Image</DialogTitle>
        <DialogContent>
          <TextField
            label="Name" fullWidth margin="normal" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} required
          />
          <TextField
            select label="Base Gold Image" fullWidth margin="normal"
            value={form.gold_image_id}
            onChange={(e) => setForm({ ...form, gold_image_id: e.target.value })}
          >
            <MenuItem value="">None</MenuItem>
            {(goldImages as GoldImage[]).map((g) => (
              <MenuItem key={g.id} value={String(g.id)}>{g.name}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Description" fullWidth margin="normal" value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <TextField
            label="Dockerfile" fullWidth margin="normal" multiline rows={6}
            value={form.dockerfile}
            onChange={(e) => setForm({ ...form, dockerfile: e.target.value })}
            placeholder="FROM base-image:latest&#10;COPY . /app"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate}
            disabled={!form.name || submitting}>
            {submitting ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Build Dialog */}
      <Dialog open={buildOpen !== null} onClose={() => setBuildOpen(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Trigger Build</DialogTitle>
        <DialogContent>
          <TextField
            label="Version Tag" fullWidth margin="normal" value={buildForm.version_tag}
            onChange={(e) => setBuildForm({ ...buildForm, version_tag: e.target.value })}
          />
          <TextField
            label="Architecture" fullWidth margin="normal" value={buildForm.arch}
            onChange={(e) => setBuildForm({ ...buildForm, arch: e.target.value })}
            placeholder="amd64, arm64, arm/v7"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBuildOpen(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleBuild} disabled={submitting}>
            {submitting ? <CircularProgress size={20} /> : 'Build'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
