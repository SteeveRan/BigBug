/**
 * @file Settings/AuditLog/index.tsx
 * @description Audit log viewer page with filters, pagination, and detail dialog.
 *              Shows all mutating operations across the system.
 * @dependencies @mui/material, ../../store/api, ../../types
 * @relatedFiles ../../store/api.ts, ../../types/index.ts
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  CircularProgress,
  Pagination,
} from '@mui/material';
import type { AuditLog } from '../../../types';
import { useGetAuditLogsQuery } from '../../../store/api';

const ACTION_COLORS: Record<string, 'success' | 'primary' | 'error' | 'secondary' | 'warning'> = {
  create: 'success',
  update: 'primary',
  delete: 'error',
  login: 'secondary',
  logout: 'secondary',
  sync: 'warning',
  build: 'warning',
};

const ACTION_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'create', label: 'Create' },
  { value: 'update', label: 'Update' },
  { value: 'delete', label: 'Delete' },
  { value: 'login', label: 'Login' },
  { value: 'logout', label: 'Logout' },
  { value: 'sync', label: 'Sync' },
  { value: 'build', label: 'Build' },
];

const RESOURCE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'auth', label: 'Auth' },
  { value: 'user', label: 'User' },
  { value: 'role', label: 'Role' },
  { value: 'mirror', label: 'Mirror' },
  { value: 'integration', label: 'Integration' },
  { value: 'pipeline', label: 'Pipeline' },
  { value: 'oidc_config', label: 'OIDC Config' },
];

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString();
}

export default function AuditLogPage() {
  const [action, setAction] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [filters, setFilters] = useState<Record<string, string | number>>({ page: 1, page_size: 50 });

  const { data, isLoading, isFetching } = useGetAuditLogsQuery(filters);

  const handleApplyFilters = useCallback(() => {
    const params: Record<string, string | number> = { page: 1, page_size: 50 };
    if (action) params.action = action;
    if (resourceType) params.resource_type = resourceType;
    if (dateFrom) params.date_from = new Date(dateFrom).toISOString();
    if (dateTo) params.date_to = new Date(dateTo).toISOString();
    setFilters(params);
    setPage(1);
  }, [action, resourceType, dateFrom, dateTo]);

  const handlePageChange = useCallback(
    (_: React.ChangeEvent<unknown>, value: number) => {
      setPage(value);
      setFilters((prev) => ({ ...prev, page: value }));
    },
    [],
  );

  const pages = data ? Math.ceil(data.total / 50) : 1;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Audit Log
      </Typography>

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          label="Date From"
          type="datetime-local"
          size="small"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          label="Date To"
          type="datetime-local"
          size="small"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          select
          label="Action"
          size="small"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          sx={{ minWidth: 130 }}
        >
          {ACTION_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Resource Type"
          size="small"
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
          sx={{ minWidth: 160 }}
        >
          {RESOURCE_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </TextField>
        <Button variant="contained" onClick={handleApplyFilters} disabled={isFetching}>
          Apply Filters
        </Button>
      </Box>

      {/* Loading */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Empty state */}
      {!isLoading && data && data.items.length === 0 && (
        <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
          No audit logs found
        </Typography>
      )}

      {/* Table */}
      {!isLoading && data && data.items.length > 0 && (
        <>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>Action</TableCell>
                  <TableCell>Resource Type</TableCell>
                  <TableCell>Resource Name</TableCell>
                  <TableCell>Details</TableCell>
                  <TableCell>IP Address</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.map((log) => (
                  <TableRow key={log.id} hover>
                    <TableCell>{formatTimestamp(log.created_at)}</TableCell>
                    <TableCell>{log.username}</TableCell>
                    <TableCell>
                      <Chip
                        label={log.action}
                        size="small"
                        color={ACTION_COLORS[log.action] || 'default'}
                      />
                    </TableCell>
                    <TableCell>{log.resource_type}</TableCell>
                    <TableCell>{log.resource_name || '-'}</TableCell>
                    <TableCell>
                      {log.details ? (
                        <Button size="small" onClick={() => setSelectedLog(log)}>
                          View
                        </Button>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>{log.ip_address || '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Pagination */}
          {pages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Pagination count={pages} page={page} onChange={handlePageChange} />
            </Box>
          )}
        </>
      )}

      {/* Details Dialog */}
      <Dialog open={Boolean(selectedLog)} onClose={() => setSelectedLog(null)} maxWidth="md" fullWidth>
        <DialogTitle>Audit Log Details</DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Timestamp: {selectedLog && formatTimestamp(selectedLog.created_at)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              User: {selectedLog?.username}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Action: {selectedLog?.action} | Resource: {selectedLog?.resource_type}
              {selectedLog?.resource_name ? ` / ${selectedLog.resource_name}` : ''}
            </Typography>
          </Box>
          <Paper
            variant="outlined"
            sx={{ p: 2, bgcolor: 'grey.100', maxHeight: 400, overflow: 'auto' }}
          >
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {selectedLog?.details ? JSON.stringify(selectedLog.details, null, 2) : 'No details'}
            </pre>
          </Paper>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedLog(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
