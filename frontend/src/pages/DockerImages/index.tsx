/**
 * @file index.tsx
 * @description Страница списка Docker Images: таблица, модальное окно с двухшаговым добавлением (анализ → подтверждение)
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Table,
  Flex,
  Modal,
  Input,
  App,
  Tooltip,
  Space,
  Tag,
  Select,
  Alert,
  Spin,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  useListDockerImagesQuery,
  useCreateDockerImageMutation,
  useAnalyzeDockerImageMutation,
} from '../../store/api';
import { DockerImageSource, AnalyzeImageResponse, DockerRegistryInstance } from '../../types';

export function DockerImagesPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { data: sources = [], isLoading } = useListDockerImagesQuery();
  const [createSource] = useCreateDockerImageMutation();
  const [analyzeDockerImage] = useAnalyzeDockerImageMutation();

  // ── Dialog state ──────────────────────────────────────────────────────────
  const [dialogOpen, setDialogOpen] = useState(false);
  const [imageName, setImageName] = useState('');
  const [step, setStep] = useState<'input' | 'analyze'>('input');
  const [analysis, setAnalysis] = useState<AnalyzeImageResponse | null>(null);
  const [selectedRegistryId, setSelectedRegistryId] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // ── Helpers ───────────────────────────────────────────────────────────────

  const resetForm = () => {
    setImageName('');
    setStep('input');
    setAnalysis(null);
    setSelectedRegistryId(null);
    setAnalysisError(null);
  };

  const handleOpenDialog = () => {
    resetForm();
    setDialogOpen(true);
  };

  // ── Step 1: Analyze image name ────────────────────────────────────────────

  const handleAnalyze = async () => {
    const trimmed = imageName.trim();
    if (!trimmed) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await analyzeDockerImage({ image_name: trimmed }).unwrap();
      setAnalysis(result);
      setSelectedRegistryId(result.suggested_registry?.id ?? null);
      setStep('analyze');
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'data' in err
          ? (err as { data?: { detail?: string } }).data?.detail
          : undefined;
      setAnalysisError(detail || 'Failed to analyze image');
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Step 2: Confirm & create ──────────────────────────────────────────────

  const handleCreate = async () => {
    if (!analysis) return;
    setSubmitting(true);
    try {
      const selectedRegistry = analysis.compatible_registries.find(
        (r) => r.id === selectedRegistryId
      );
      await createSource({
        name: analysis.image_name,
        registry_url: selectedRegistry?.url || analysis.detected_registry_host,
        image_name: analysis.normalized_image,
        registry_instance_id: selectedRegistryId ?? undefined,
      }).unwrap();
      message.success('Docker image added successfully');
      setDialogOpen(false);
      resetForm();
    } catch {
      // error handled by RTK Query
    } finally {
      setSubmitting(false);
    }
  };

  const handleBack = () => {
    setStep('input');
    setAnalysis(null);
    setSelectedRegistryId(null);
    setAnalysisError(null);
  };

  const handleCancel = () => {
    setDialogOpen(false);
    resetForm();
  };

  // ── Table columns ─────────────────────────────────────────────────────────

  const columns: ColumnsType<DockerImageSource> = [
    {
      title: 'Name',
      key: 'name',
      width: 180,
      render: (_: unknown, record: DockerImageSource) => (
        <Flex vertical>
          <Typography.Text strong>{record.name}</Typography.Text>
          {record.description && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {record.description}
            </Typography.Text>
          )}
        </Flex>
      ),
    },
    {
      title: 'Registry URL',
      dataIndex: 'registry_url',
      key: 'registry_url',
      width: 200,
      render: (val: string) => (
        <Typography.Text code style={{ fontSize: '0.8rem' }} ellipsis>
          {val}
        </Typography.Text>
      ),
    },
    {
      title: 'Target Registry',
      key: 'target_registry',
      width: 200,
      render: (_: unknown, record: DockerImageSource) => {
        if (!record.target_registry_url) {
          return (
            <Typography.Text type="secondary" disabled>
              Not configured
            </Typography.Text>
          );
        }
        const short = (() => {
          try {
            return new URL(record.target_registry_url).hostname;
          } catch {
            return record.target_registry_url;
          }
        })();
        return (
          <Typography.Text code style={{ fontSize: '0.8rem' }} ellipsis>
            {short}
          </Typography.Text>
        );
      },
    },
    {
      title: 'Mirroring Status',
      key: 'mirroring_status',
      width: 140,
      render: (_: unknown, record: DockerImageSource) => {
        if (!record.target_registry_url) {
          return <Tag>Not configured</Tag>;
        }
        return <Tag color="green">Ready</Tag>;
      },
    },
    {
      title: 'Sync Schedule',
      key: 'sync_schedule',
      width: 130,
      render: (_: unknown, record: DockerImageSource) => {
        if (!record.target_registry_url) {
          return <Typography.Text type="secondary">—</Typography.Text>;
        }
        return <Typography.Text>Configured</Typography.Text>;
      },
    },
    {
      title: 'Project Count',
      key: 'project_count',
      width: 120,
      align: 'center',
      render: () => <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Tag Count',
      key: 'tag_count',
      width: 100,
      align: 'center',
      render: () => <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Last Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (val: string) => (val ? new Date(val).toLocaleString() : '—'),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 80,
      align: 'right',
      render: (_: unknown, record: DockerImageSource) => (
        <Tooltip title="Go to details">
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/docker-images/${record.id}`);
            }}
          />
        </Tooltip>
      ),
    },
  ];

  // ── Registry select options ───────────────────────────────────────────────

  const registryOptions = (analysis?.compatible_registries || []).map(
    (r: DockerRegistryInstance) => ({
      label: `${r.name} (${r.url})`,
      value: r.id,
    })
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Docker Images
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenDialog}>
          Add Image
        </Button>
      </Flex>

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      <Card>
        <Table
          columns={columns}
          dataSource={sources as DockerImageSource[]}
          rowKey="id"
          loading={isLoading}
          onRow={(record) => ({
            onClick: () => navigate(`/docker-images/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          pagination={false}
          locale={{ emptyText: 'No Docker image sources yet. Add an image to get started.' }}
        />
      </Card>

      {/* ── Add Image Modal ─────────────────────────────────────────────────── */}
      <Modal
        title="Add Docker Image"
        open={dialogOpen}
        onCancel={handleCancel}
        footer={
          step === 'input'
            ? [
                <Button key="cancel" onClick={handleCancel}>
                  Cancel
                </Button>,
                <Button
                  key="analyze"
                  type="primary"
                  loading={analyzing}
                  disabled={!imageName.trim()}
                  onClick={handleAnalyze}
                >
                  Analyze
                </Button>,
              ]
            : [
                <Button key="back" onClick={handleBack}>
                  Back
                </Button>,
                <Button key="cancel" onClick={handleCancel}>
                  Cancel
                </Button>,
                <Button
                  key="create"
                  type="primary"
                  loading={submitting}
                  disabled={!selectedRegistryId}
                  onClick={handleCreate}
                >
                  Add Image
                </Button>,
              ]
        }
      >
        {/* ── Step 1: Input ─────────────────────────────────────────────────── */}
        {step === 'input' && (
          <Flex vertical gap={16}>
            <Typography.Text>
              Enter an image name to detect its registry and compatible registries.
            </Typography.Text>
            <Input
              placeholder="e.g. nginx:latest or quay.io/prometheus/node-exporter:latest"
              value={imageName}
              onChange={(e) => {
                setImageName(e.target.value);
                setAnalysisError(null);
              }}
              onPressEnter={handleAnalyze}
              size="large"
              autoFocus
            />
            {analyzing && (
              <Flex justify="center">
                <Spin tip="Analyzing image..." />
              </Flex>
            )}
            {analysisError && <Alert type="error" title={analysisError} closable />}
          </Flex>
        )}

        {/* ── Step 2: Review & Confirm ──────────────────────────────────────── */}
        {step === 'analyze' && analysis && (
          <Flex vertical gap={16}>
            {/* Normalized image */}
            <Flex vertical gap={4}>
              <Typography.Text strong>Normalized Image</Typography.Text>
              <Typography.Text code>{analysis.normalized_image}</Typography.Text>
            </Flex>

            {/* Detected registry */}
            <Flex vertical gap={4}>
              <Typography.Text strong>Detected Registry</Typography.Text>
              <Space>
                <Tag>{analysis.detected_registry_host}</Tag>
                <Tag color="blue">{analysis.detected_provider}</Tag>
              </Space>
            </Flex>

            {/* Registry selection */}
            <Flex vertical gap={4}>
              <Typography.Text strong>Target Registry</Typography.Text>
              <Select
                style={{ width: '100%' }}
                options={registryOptions}
                value={selectedRegistryId}
                onChange={(val) => setSelectedRegistryId(val)}
                placeholder="Select a registry..."
              />
              <Typography.Text type="secondary">
                The registry that will be used to pull this image
              </Typography.Text>
            </Flex>

            {/* New registry needed warning */}
            {analysis.is_new_registry_needed && (
              <Alert
                type="warning"
                showIcon
                message="No matching registry found"
                description="You may need to add one in Settings → Integrations → External Registries"
              />
            )}
          </Flex>
        )}
      </Modal>
    </Flex>
  );
}
