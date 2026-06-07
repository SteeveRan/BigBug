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
import { Add as AddIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import {
  useListHelmChartsQuery,
  useCreateHelmChartMutation,
  useIndexHelmChartMutation,
} from '../../store/api';
import { HelmChartSource } from '../../types';
import { StatusChip } from '../../components/StatusChip';

export function HelmChartsPage() {
  const navigate = useNavigate();
  const { data: charts = [], isLoading } = useListHelmChartsQuery();
  const [createChart] = useCreateHelmChartMutation();
  const [indexChart] = useIndexHelmChartMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ name: '', repo_url: '', description: '' });
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createChart(form).unwrap();
      setDialogOpen(false);
      setForm({ name: '', repo_url: '', description: '' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" fontWeight="bold">
          Helm Charts
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setForm({ name: '', repo_url: '', description: '' });
            setDialogOpen(true);
          }}
        >
          Add Chart Source
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
                <TableCell>Repository URL</TableCell>
                <TableCell>Last Synced</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(charts as HelmChartSource[]).map((chart) => (
                <TableRow
                  key={chart.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/helm-charts/${chart.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {chart.name}
                    </Typography>
                    {chart.description && (
                      <Typography variant="caption" color="text.secondary">
                        {chart.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
                    >
                      {chart.repo_url}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {chart.last_synced_at ? new Date(chart.last_synced_at).toLocaleString() : '—'}
                  </TableCell>
                  <TableCell>
                    <StatusChip
                      statusFlag={chart.status_flag as 0 | 1 | 2 | 3 | 4}
                      statusText={chart.status_text}
                    />
                  </TableCell>
                  <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                    <Tooltip title="Re-index now">
                      <IconButton size="small" onClick={() => indexChart(chart.id)}>
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {charts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    <Typography color="text.secondary" py={3}>
                      No Helm chart sources yet. Add one to get started.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Helm Chart Source</DialogTitle>
        <DialogContent>
          <TextField
            label="Name"
            fullWidth
            margin="normal"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="stable"
            required
          />
          <TextField
            label="Repository URL"
            fullWidth
            margin="normal"
            value={form.repo_url}
            onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
            placeholder="https://charts.helm.sh/stable"
            required
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
            disabled={!form.name || !form.repo_url || submitting}
          >
            {submitting ? <CircularProgress size={20} /> : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
