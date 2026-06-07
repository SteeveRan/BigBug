/**
 * @file Settings/Authentication/index.tsx
 * @description Settings page for managing OIDC/SSO authentication configuration.
 *              Provides UI for configuring Keycloak/SSO issuer, client credentials,
 *              and role mapping between provider roles and BigBug roles.
 * @dependencies @mui/material, @mui/icons-material, ../../store/api, ../../components/PermissionGate
 * @relatedFiles ../../store/api.ts, ../../types/index.ts, ../../components/PermissionGate.tsx
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Switch,
  Button,
  Divider,
  Alert,
  CircularProgress,
  Snackbar,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  FormControlLabel,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon } from '@mui/icons-material';

import type { OIDCConfigUpdate } from '../../../types';
import { useGetOidcConfigQuery, useUpdateOidcConfigMutation } from '../../../store/api';

// ─── Constants ───────────────────────────────────────────────────────────────

const MASKED_SECRET = '********';
const SECRET_PLACEHOLDER = 'Enter new secret to change';

// ─── Snackbar state ──────────────────────────────────────────────────────────

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

const EMPTY_SNACKBAR: SnackbarState = { open: false, message: '', severity: 'success' };

// ─── Role mapping entry ──────────────────────────────────────────────────────

interface RoleMappingEntry {
  id: number; // local id for React key
  providerRole: string;
  bigbugRole: string;
}

let nextMappingId = 0;

function createMappingEntry(providerRole = '', bigbugRole = ''): RoleMappingEntry {
  return { id: ++nextMappingId, providerRole, bigbugRole };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Convert Record<string, string> to RoleMappingEntry[] */
function recordToEntries(rm: Record<string, string> | undefined | null): RoleMappingEntry[] {
  if (!rm || Object.keys(rm).length === 0) return [];
  return Object.entries(rm).map(([providerRole, bigbugRole]) => ({
    id: ++nextMappingId,
    providerRole,
    bigbugRole,
  }));
}

/** Convert RoleMappingEntry[] to Record<string, string> */
function entriesToRecord(entries: RoleMappingEntry[]): Record<string, string> {
  const record: Record<string, string> = {};
  for (const entry of entries) {
    const key = entry.providerRole.trim();
    if (key) {
      record[key] = entry.bigbugRole.trim();
    }
  }
  return record;
}

// ─── Main component ──────────────────────────────────────────────────────────

export function AuthenticationSettings() {
  const { data: config, isLoading, isError } = useGetOidcConfigQuery();
  const [updateConfig, { isLoading: isSaving }] = useUpdateOidcConfigMutation();

  const [snackbar, setSnackbar] = useState<SnackbarState>(EMPTY_SNACKBAR);

  // Form state
  const [enabled, setEnabled] = useState(false);
  const [issuerUrl, setIssuerUrl] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [frontendClientId, setFrontendClientId] = useState('');
  const [publicUrl, setPublicUrl] = useState('');
  const [mappings, setMappings] = useState<RoleMappingEntry[]>([]);

  // Track whether the secret was masked (so we know user hasn't changed it)
  const [secretWasMasked, setSecretWasMasked] = useState(false);

  // Track original values for dirty detection
  const [originalValues, setOriginalValues] = useState<{
    enabled: boolean;
    issuerUrl: string;
    clientId: string;
    clientSecret: string;
    frontendClientId: string;
    publicUrl: string;
    mappingsJson: string;
  } | null>(null);

  // Populate form when data loads
  useEffect(() => {
    if (!config) return;

    const secretValue = config.client_secret === MASKED_SECRET ? '' : config.client_secret;
    const isMasked = config.client_secret === MASKED_SECRET;

    setEnabled(config.enabled);
    setIssuerUrl(config.issuer_url ?? '');
    setClientId(config.client_id ?? '');
    setClientSecret(secretValue);
    setSecretWasMasked(isMasked);
    setFrontendClientId(config.frontend_client_id ?? '');
    setPublicUrl(config.public_url ?? '');
    setMappings(recordToEntries(config.role_mapping));

    setOriginalValues({
      enabled: config.enabled,
      issuerUrl: config.issuer_url ?? '',
      clientId: config.client_id ?? '',
      clientSecret: secretValue,
      frontendClientId: config.frontend_client_id ?? '',
      publicUrl: config.public_url ?? '',
      mappingsJson: JSON.stringify(config.role_mapping ?? {}),
    });
  }, [config]);

  // Dirty detection
  const isDirty = useMemo(() => {
    if (!originalValues) return false;
    return (
      originalValues.enabled !== enabled ||
      originalValues.issuerUrl !== issuerUrl ||
      originalValues.clientId !== clientId ||
      originalValues.clientSecret !== clientSecret ||
      originalValues.frontendClientId !== frontendClientId ||
      originalValues.publicUrl !== publicUrl ||
      originalValues.mappingsJson !== JSON.stringify(entriesToRecord(mappings))
    );
  }, [
    originalValues,
    enabled,
    issuerUrl,
    clientId,
    clientSecret,
    frontendClientId,
    publicUrl,
    mappings,
  ]);

  const showSnackbar = useCallback((message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  }, []);

  const hideSnackbar = useCallback(() => {
    setSnackbar(EMPTY_SNACKBAR);
  }, []);

  // ─── Role mapping handlers ─────────────────────────────────────────────────

  const handleAddMapping = () => {
    setMappings((prev) => [...prev, createMappingEntry()]);
  };

  const handleRemoveMapping = (id: number) => {
    setMappings((prev) => prev.filter((m) => m.id !== id));
  };

  const handleMappingChange = (id: number, field: 'providerRole' | 'bigbugRole', value: string) => {
    setMappings((prev) => prev.map((m) => (m.id === id ? { ...m, [field]: value } : m)));
  };

  // ─── Submit handler ────────────────────────────────────────────────────────

  const handleSave = async () => {
    const payload: OIDCConfigUpdate = {};

    if (originalValues?.enabled !== enabled) {
      payload.enabled = enabled;
    }

    if (originalValues?.issuerUrl !== issuerUrl) {
      payload.issuer_url = issuerUrl;
    }

    if (originalValues?.clientId !== clientId) {
      payload.client_id = clientId;
    }

    // Only send client_secret if user actually typed something
    if (clientSecret !== '') {
      payload.client_secret = clientSecret;
    }

    if (originalValues?.frontendClientId !== frontendClientId) {
      payload.frontend_client_id = frontendClientId;
    }

    if (originalValues?.publicUrl !== publicUrl) {
      payload.public_url = publicUrl || null;
    }

    const currentMappings = entriesToRecord(mappings);
    if (originalValues?.mappingsJson !== JSON.stringify(currentMappings)) {
      payload.role_mapping = currentMappings;
    }

    // Don't send empty update
    if (Object.keys(payload).length === 0) return;

    try {
      await updateConfig(payload).unwrap();
      showSnackbar('Settings saved successfully', 'success');

      // Update original values after successful save
      setOriginalValues({
        enabled,
        issuerUrl,
        clientId,
        clientSecret,
        frontendClientId,
        publicUrl,
        mappingsJson: JSON.stringify(entriesToRecord(mappings)),
      });
      setSecretWasMasked(false);
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'data' in err
          ? ((err as { data: { detail?: string } }).data?.detail ?? 'Failed to save settings')
          : 'Failed to save settings';
      showSnackbar(message, 'error');
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isError) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Authentication Settings
        </Typography>
        <Alert severity="error">
          Failed to load authentication configuration. Please try again later.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Authentication Settings
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Configure OIDC / SSO authentication provider (Keycloak) and role mapping between external
        roles and BigBug internal roles.
      </Typography>

      {/* ── OIDC / SSO Configuration Section ─────────────────────────────── */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">OIDC / SSO Configuration</Typography>
          <FormControlLabel
          control={
            <Switch
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              slotProps={{ input: { 'aria-label': 'Enable SSO / OIDC' } }}
            />
          }
            label={enabled ? 'Enabled' : 'Disabled'}
            labelPlacement="start"
          />
        </Box>

        <Divider sx={{ mb: 3 }} />

        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 3,
          }}
        >
          <Box sx={{ flex: '1 1 360px', maxWidth: '100%' }}>
            <TextField
              label="Issuer URL"
              fullWidth
              value={issuerUrl}
              onChange={(e) => setIssuerUrl(e.target.value)}
              placeholder="https://keycloak.example.com/realms/myrealm"
              helperText="The OIDC issuer URL of your authentication provider"
              disabled={isSaving}
            />
          </Box>

          <Box sx={{ flex: '1 1 360px', maxWidth: '100%' }}>
            <TextField
              label="Public URL"
              fullWidth
              value={publicUrl}
              onChange={(e) => setPublicUrl(e.target.value)}
              placeholder="https://auth.example.com"
              helperText="Optional. Public-facing URL for the auth provider (if different from issuer)"
              disabled={isSaving}
            />
          </Box>

          <Box sx={{ flex: '1 1 360px', maxWidth: '100%' }}>
            <TextField
              label="Backend Client ID"
              fullWidth
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="bigbug-backend"
              helperText="OIDC client ID for backend server-to-server communication"
              disabled={isSaving}
            />
          </Box>

          <Box sx={{ flex: '1 1 360px', maxWidth: '100%' }}>
            <TextField
              label="Frontend Client ID"
              fullWidth
              value={frontendClientId}
              onChange={(e) => setFrontendClientId(e.target.value)}
              placeholder="bigbug-frontend"
              helperText="OIDC client ID for frontend SPA (public client)"
              disabled={isSaving}
            />
          </Box>

          <Box sx={{ flex: '1 1 360px', maxWidth: '100%' }}>
            <TextField
              label="Client Secret"
              fullWidth
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              type="password"
              placeholder={secretWasMasked ? SECRET_PLACEHOLDER : ''}
              helperText={
                secretWasMasked
                  ? 'Secret is stored. Enter a new value to change.'
                  : 'OIDC client secret (confidential client)'
              }
              disabled={isSaving}
            />
          </Box>
        </Box>
      </Paper>

      {/* ── Role Mapping Section ─────────────────────────────────────────── */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">Role Mapping</Typography>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleAddMapping}
            disabled={isSaving}
          >
            Add Mapping
          </Button>
        </Box>

        <Divider sx={{ mb: 2 }} />

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Map provider roles (from your OIDC provider) to BigBug internal roles.
        </Typography>

        {mappings.length === 0 ? (
          <Typography
            color="text.secondary"
            sx={{ py: 2, textAlign: 'center', fontStyle: 'italic' }}
          >
            No role mappings configured. Add a mapping to map external roles to BigBug roles.
          </Typography>
        ) : (
          <TableContainer>
            <Table aria-label="Role mappings table" size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Provider Role</TableCell>
                  <TableCell>BigBug Role</TableCell>
                  <TableCell align="right" sx={{ width: 60 }}>
                    Actions
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mappings.map((entry) => (
                  <TableRow key={entry.id} hover>
                    <TableCell>
                      <TextField
                        size="small"
                        fullWidth
                        value={entry.providerRole}
                        onChange={(e) =>
                          handleMappingChange(entry.id, 'providerRole', e.target.value)
                        }
                        placeholder="e.g. bigbug-admin"
                        disabled={isSaving}
                        inputProps={{ 'aria-label': `Provider role for mapping ${entry.id}` }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        fullWidth
                        value={entry.bigbugRole}
                        onChange={(e) =>
                          handleMappingChange(entry.id, 'bigbugRole', e.target.value)
                        }
                        placeholder="e.g. admin"
                        disabled={isSaving}
                        inputProps={{ 'aria-label': `BigBug role for mapping ${entry.id}` }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Remove mapping">
                        <IconButton
                          size="small"
                          onClick={() => handleRemoveMapping(entry.id)}
                          disabled={isSaving}
                          aria-label={`Remove mapping ${entry.providerRole || '(empty)'}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* ── Save Button ──────────────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="contained"
          size="large"
          onClick={handleSave}
          disabled={!isDirty || isSaving}
        >
          {isSaving ? <CircularProgress size={24} color="inherit" /> : 'Save Changes'}
        </Button>
      </Box>

      {/* ── Snackbar ─────────────────────────────────────────────────────── */}
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

export default AuthenticationSettings;
