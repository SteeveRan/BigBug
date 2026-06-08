/**
 * @file Settings/AuditLog/index.tsx
 * @description Audit log viewer page with filters, pagination, and detail modal.
 *              Shows all mutating operations across the system.
 * @dependencies antd, ../../store/api, ../../types
 * @relatedFiles ../../store/api.ts, ../../types/index.ts
 */

import { useState, useCallback } from 'react';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Spin,
  Modal,
  Input,
  Select,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { AuditLog } from '../../../types';
import { useGetAuditLogsQuery } from '../../../store/api';

const ACTION_COLORS: Record<string, string> = {
  create: 'green',
  update: 'blue',
  delete: 'red',
  login: 'purple',
  logout: 'purple',
  sync: 'orange',
  build: 'orange',
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
  const [filters, setFilters] = useState<Record<string, string | number>>({
    page: 1,
    page_size: 50,
  });

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

  const pages = data ? Math.ceil(data.total / 50) : 1;

  const columns: ColumnsType<AuditLog> = [
    {
      title: 'Timestamp',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => formatTimestamp(text),
    },
    { title: 'User', dataIndex: 'username', key: 'username' },
    {
      title: 'Action',
      dataIndex: 'action',
      key: 'action',
      render: (text: string) => (
        <Tag color={ACTION_COLORS[text] || 'default'}>{text}</Tag>
      ),
    },
    { title: 'Resource Type', dataIndex: 'resource_type', key: 'resource_type' },
    {
      title: 'Resource Name',
      key: 'resource_name',
      render: (_: unknown, record: AuditLog) => record.resource_name || '-',
    },
    {
      title: 'Details',
      key: 'details',
      render: (_: unknown, record: AuditLog) =>
        record.details ? (
          <Button size="small" type="link" onClick={() => setSelectedLog(record)}>
            View
          </Button>
        ) : (
          '-'
        ),
    },
    {
      title: 'IP Address',
      key: 'ip_address',
      render: (_: unknown, record: AuditLog) => record.ip_address || '-',
    },
  ];

  return (
    <Flex vertical gap={16}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Audit Log
      </Typography.Title>

      {/* Filters */}
      <Flex gap={12} wrap="wrap" align="center">
        <Input
          type="datetime-local"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          style={{ width: 200 }}
        />
        <Input
          type="datetime-local"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          style={{ width: 200 }}
        />
        <Select
          placeholder="Action"
          value={action || undefined}
          onChange={(v) => setAction(v ?? '')}
          options={ACTION_OPTIONS}
          style={{ minWidth: 130 }}
        />
        <Select
          placeholder="Resource Type"
          value={resourceType || undefined}
          onChange={(v) => setResourceType(v ?? '')}
          options={RESOURCE_OPTIONS}
          style={{ minWidth: 160 }}
        />
        <Button type="primary" onClick={handleApplyFilters} loading={isFetching}>
          Apply Filters
        </Button>
      </Flex>

      {/* Loading */}
      {isLoading && (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin />
        </Flex>
      )}

      {/* Empty state */}
      {!isLoading && data && data.items.length === 0 && (
        <Typography.Text type="secondary" style={{ padding: '40px 0', textAlign: 'center', display: 'block' }}>
          No audit logs found
        </Typography.Text>
      )}

      {/* Table + Pagination */}
      {!isLoading && data && data.items.length > 0 && (
        <Card>
          <Table
            columns={columns}
            dataSource={data.items}
            rowKey="id"
            pagination={
              pages > 1
                ? {
                    current: page,
                    total: data.total,
                    pageSize: 50,
                    onChange: (p) => {
                      setPage(p);
                      setFilters((prev) => ({ ...prev, page: p }));
                    },
                    showSizeChanger: false,
                  }
                : false
            }
            size="small"
          />
        </Card>
      )}

      {/* Details Modal */}
      <Modal
        title="Audit Log Details"
        open={Boolean(selectedLog)}
        onCancel={() => setSelectedLog(null)}
        footer={[
          <Button key="close" onClick={() => setSelectedLog(null)}>
            Close
          </Button>,
        ]}
        width={640}
      >
        <Flex vertical gap={8}>
          <Typography.Text>
            <strong>Timestamp:</strong> {selectedLog && formatTimestamp(selectedLog.created_at)}
          </Typography.Text>
          <Typography.Text>
            <strong>User:</strong> {selectedLog?.username}
          </Typography.Text>
          <Typography.Text>
            <strong>Action:</strong> {selectedLog?.action} | <strong>Resource:</strong>{' '}
            {selectedLog?.resource_type}
            {selectedLog?.resource_name ? ` / ${selectedLog.resource_name}` : ''}
          </Typography.Text>
          <Card
            size="small"
            styles={{ body: { backgroundColor: '#fafafa', maxHeight: 400, overflow: 'auto' } }}
          >
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {selectedLog?.details ? JSON.stringify(selectedLog.details, null, 2) : 'No details'}
            </pre>
          </Card>
        </Flex>
      </Modal>
    </Flex>
  );
}
