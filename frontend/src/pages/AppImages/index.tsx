import { useState } from 'react';
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
  Snackbar,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  Add as AddIcon,
  Build as BuildIcon,
  Security as SecurityIcon,
  Lock as LockIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import {
  useListAppImagesQuery,
  useCreateAppImageMutation,
  useTriggerAppBuildMutation,
  useScanAppImageVersionMutation,
  useListGoldImagesQuery,
  useGetHarborInstancesQuery,
  useSignAppImageVersionMutation,
} from '../../store/api';
import { VulnerabilityBadge } from '../../components/VulnerabilityBadge';
import { SignatureBadge } from '../../components/SignatureBadge';
import type { AppImage, GoldImage, ImageVersion, HarborInstance } from '../../types';

export function AppImagesPage() {
  const { data: images = [], isLoading } = useListAppImagesQuery();
  const { data: goldImages = [] } = useListGoldImagesQuery();
  const { data: harborInstances = [] } = useGetHarborInstancesQuery();
  const [createImage] = useCreateAppImageMutation();
  const [triggerBuild] = useTriggerAppBuildMutation();
  const [scanVersion] = useScanAppImageVersionMutation();
  const [signVersion] = useSignAppImageVersionMutation();

  const [createOpen, setCreateOpen] = useState(false);
  const [buildOpen, setBuildOpen] = useState<number | null>(null);
  const [scanOpen, setScanOpen] = useState<{
    imageId: number;
    versionId: number;
  } | null>(null);
  const [signOpen, setSignOpen] = useState<{
    imageId: number;
    versionId: number;
    registryUrl: string | null;
    versionTag: string;
  } | null>(null);
  const [expandedImage, setExpandedImage] = useState<number | null>(null);
  const [versions, setVersions] = useState<Record<number, ImageVersion[]>>({});
  const [loadingVersions, setLoadingVersions] = useState<Set<number>>(new Set());

  const [form, setForm] = useState({
    name: '',
    description: '',
    dockerfile: '',
    gold_image_id: '',
  });
  const [buildForm, setBuildForm] = useState({ version_tag: 'latest', arch: 'amd64' });
  const [scanForm, setScanForm] = useState({
    harbor_instance_id: '',
    project_name: '',
    repository_name: '',
    artifact_digest: '',
  });
  const [signForm, setSignForm] = useState({
    image_reference: '',
    cosign_private_key: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createImage({
        ...form,
        gold_image_id: form.gold_image_id ? Number(form.gold_image_id) : undefined,
      }).unwrap();
      setCreateOpen(false);
      setForm({ name: '', description: '', dockerfile: '', gold_image_id: '' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleBuild = async () => {
    if (buildOpen === null) return;
    setSubmitting(true);
    try {
      await triggerBuild({ id: buildOpen, ...buildForm }).unwrap();
      setBuildOpen(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleScan = async () => {
    if (scanOpen === null) return;
    setSubmitting(true);
    try {
      await scanVersion({
        imageId: scanOpen.imageId,
        versionId: scanOpen.versionId,
        harbor_instance_id: Number(scanForm.harbor_instance_id),
        project_name: scanForm.project_name,
        repository_name: scanForm.repository_name,
        artifact_digest: scanForm.artifact_digest,
      }).unwrap();
      setScanOpen(null);
      setSnackbar({ open: true, message: 'Scan triggered successfully', severity: 'success' });
    } catch {
      setSnackbar({ open: true, message: 'Scan trigger failed', severity: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSign = async () => {
    if (signOpen === null) return;
    setSubmitting(true);
    try {
      await signVersion({
        imageId: signOpen.imageId,
        versionId: signOpen.versionId,
        image_reference: signForm.image_reference,
        cosign_private_key: signForm.cosign_private_key,
      }).unwrap();
      setSignOpen(null);
      setSnackbar({ open: true, message: 'Image signed successfully', severity: 'success' });
    } catch {
      setSnackbar({ open: true, message: 'Image signing failed', severity: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const toggleExpand = async (imageId: number) => {
    if (expandedImage === imageId) {
      setExpandedImage(null);
      return;
    }
    setExpandedImage(imageId);
    if (!versions[imageId]) {
      setLoadingVersions((prev) => new Set(prev).add(imageId));
      try {
        const resp = await fetch(
          `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/app-images/${imageId}/versions`,
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
            },
          },
        );
        const data = await resp.json();
        setVersions((prev) => ({ ...prev, [imageId]: data }));
      } finally {
        setLoadingVersions((prev) => {
          const next = new Set(prev);
          next.delete(imageId);
          return next;
        });
      }
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">
          App Images
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          New App Image
        </Button>
      </Box>

      {isLoading ? (
        <CircularProgress />
      ) : (
        <Grid container spacing={3}>
          {(images as AppImage[]).map((image) => {
            const goldImage = (goldImages as GoldImage[]).find((g) => g.id === image.gold_image_id);
            return (
              <Grid key={image.id} size={{ xs: 12, sm: 6, md: 4 }}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" mb={1}>
                      {image.name}
                    </Typography>
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
                  <CardActions sx={{ justifyContent: 'space-between' }}>
                    <Box>
                      <Button
                        size="small"
                        startIcon={<BuildIcon />}
                        onClick={() => {
                          setBuildForm({ version_tag: 'latest', arch: 'amd64' });
                          setBuildOpen(image.id);
                        }}
                      >
                        Build
                      </Button>
                    </Box>
                    <IconButton
                      size="small"
                      onClick={() => toggleExpand(image.id)}
                      aria-label="Toggle versions"
                    >
                      {expandedImage === image.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </IconButton>
                  </CardActions>

                  {/* Versions table (expandable) */}
                  <Collapse in={expandedImage === image.id} timeout="auto" unmountOnExit>
                    <Box sx={{ px: 2, pb: 2 }}>
                      <Typography variant="subtitle2" fontWeight="bold" mb={1}>
                        Versions
                      </Typography>
                      {loadingVersions.has(image.id) ? (
                        <CircularProgress size={20} />
                      ) : versions[image.id]?.length ? (
                        <TableContainer component={Paper} variant="outlined">
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Tag</TableCell>
                                <TableCell>Arch</TableCell>
                                <TableCell>Status</TableCell>
                                <TableCell>Security</TableCell>
                                <TableCell>Signature</TableCell>
                                <TableCell>Actions</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {versions[image.id].map((version) => (
                                <TableRow key={version.id}>
                                  <TableCell>{version.version_tag}</TableCell>
                                  <TableCell>{version.arch}</TableCell>
                                  <TableCell>
                                    <Chip
                                      label={version.status_text || 'Pending'}
                                      size="small"
                                      color={
                                        version.status_flag === 0
                                          ? 'success'
                                          : version.status_flag === 1
                                            ? 'error'
                                            : version.status_flag === 3
                                              ? 'info'
                                              : 'default'
                                      }
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <VulnerabilityBadge
                                      count={version.vulnerabilities}
                                      severity={version.vulnerability_severity}
                                      compact
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <SignatureBadge
                                      isSigned={version.is_signed ?? false}
                                      signature={version.cosign_signature}
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <IconButton
                                      size="small"
                                      color="primary"
                                      onClick={() => {
                                        setSignForm({
                                          image_reference: version.registry_url
                                            ? `${version.registry_url}/${image.name}:${version.version_tag}`
                                            : `${image.name}:${version.version_tag}`,
                                          cosign_private_key: '',
                                        });
                                        setSignOpen({
                                          imageId: image.id,
                                          versionId: version.id,
                                          registryUrl: version.registry_url,
                                          versionTag: version.version_tag,
                                        });
                                      }}
                                      title="Sign image"
                                    >
                                      <LockIcon fontSize="small" />
                                    </IconButton>
                                    <IconButton
                                      size="small"
                                      color="primary"
                                      onClick={() => {
                                        setScanForm({
                                          harbor_instance_id: '',
                                          project_name: '',
                                          repository_name: '',
                                          artifact_digest: version.sha256_digest || '',
                                        });
                                        setScanOpen({
                                          imageId: image.id,
                                          versionId: version.id,
                                        });
                                      }}
                                      title="Scan for vulnerabilities"
                                    >
                                      <SecurityIcon fontSize="small" />
                                    </IconButton>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No versions built yet.
                        </Typography>
                      )}
                    </Box>
                  </Collapse>
                </Card>
              </Grid>
            );
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
            label="Name"
            fullWidth
            margin="normal"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <TextField
            select
            label="Base Gold Image"
            fullWidth
            margin="normal"
            value={form.gold_image_id}
            onChange={(e) => setForm({ ...form, gold_image_id: e.target.value })}
          >
            <MenuItem value="">None</MenuItem>
            {(goldImages as GoldImage[]).map((g) => (
              <MenuItem key={g.id} value={String(g.id)}>
                {g.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Description"
            fullWidth
            margin="normal"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <TextField
            label="Dockerfile"
            fullWidth
            margin="normal"
            multiline
            rows={6}
            value={form.dockerfile}
            onChange={(e) => setForm({ ...form, dockerfile: e.target.value })}
            placeholder="FROM base-image:latest&#10;COPY . /app"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!form.name || submitting}>
            {submitting ? <CircularProgress size={20} /> : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Build Dialog */}
      <Dialog open={buildOpen !== null} onClose={() => setBuildOpen(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Trigger Build</DialogTitle>
        <DialogContent>
          <TextField
            label="Version Tag"
            fullWidth
            margin="normal"
            value={buildForm.version_tag}
            onChange={(e) => setBuildForm({ ...buildForm, version_tag: e.target.value })}
          />
          <TextField
            label="Architecture"
            fullWidth
            margin="normal"
            value={buildForm.arch}
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

      {/* Scan Dialog */}
      <Dialog
        open={scanOpen !== null}
        onClose={() => setScanOpen(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Scan for Vulnerabilities</DialogTitle>
        <DialogContent>
          <TextField
            select
            label="Harbor Instance"
            fullWidth
            margin="normal"
            value={scanForm.harbor_instance_id}
            onChange={(e) =>
              setScanForm({ ...scanForm, harbor_instance_id: e.target.value })
            }
            required
          >
            {(harborInstances as HarborInstance[]).map((h) => (
              <MenuItem key={h.id} value={String(h.id)}>
                {h.name} ({h.url})
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Project Name"
            fullWidth
            margin="normal"
            value={scanForm.project_name}
            onChange={(e) => setScanForm({ ...scanForm, project_name: e.target.value })}
            required
          />
          <TextField
            label="Repository Name"
            fullWidth
            margin="normal"
            value={scanForm.repository_name}
            onChange={(e) => setScanForm({ ...scanForm, repository_name: e.target.value })}
            required
          />
          <TextField
            label="Artifact Digest (sha256)"
            fullWidth
            margin="normal"
            value={scanForm.artifact_digest}
            onChange={(e) => setScanForm({ ...scanForm, artifact_digest: e.target.value })}
            required
            placeholder="sha256:abc123..."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setScanOpen(null)}>Cancel</Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<SecurityIcon />}
            onClick={handleScan}
            disabled={
              !scanForm.harbor_instance_id ||
              !scanForm.project_name ||
              !scanForm.repository_name ||
              !scanForm.artifact_digest ||
              submitting
            }
          >
            {submitting ? <CircularProgress size={20} /> : 'Scan'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Sign Dialog */}
      <Dialog
        open={signOpen !== null}
        onClose={() => setSignOpen(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Sign Image with Cosign</DialogTitle>
        <DialogContent>
          <TextField
            label="Image Reference"
            fullWidth
            margin="normal"
            value={signForm.image_reference}
            onChange={(e) =>
              setSignForm({ ...signForm, image_reference: e.target.value })
            }
            required
            placeholder="registry.example.com/project/image:tag"
            helperText="Full image reference including registry and tag"
          />
          <TextField
            label="Cosign Private Key"
            fullWidth
            margin="normal"
            multiline
            rows={6}
            type="password"
            value={signForm.cosign_private_key}
            onChange={(e) =>
              setSignForm({ ...signForm, cosign_private_key: e.target.value })
            }
            required
            placeholder="-----BEGIN ENCRYPTED COSIGN PRIVATE KEY-----"
            helperText="PEM-encoded cosign private key. Not stored in the database."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSignOpen(null)}>Cancel</Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<LockIcon />}
            onClick={handleSign}
            disabled={!signForm.image_reference || !signForm.cosign_private_key || submitting}
          >
            {submitting ? <CircularProgress size={20} /> : 'Sign'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          severity={snackbar.severity}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
