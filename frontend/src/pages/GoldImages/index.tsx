/**
 * @file index.tsx
 * @description Страница Gold Images: карточки образов в сетке Row/Col, раскрывающиеся версии в Table, модальные окна для CRUD/scan/sign
 * @dependencies antd, @ant-design/icons, Redux store
 */
import { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  Tag,
  Flex,
  Spin,
  Modal,
  Input,
  Select,
  App,
  Row,
  Col,
  Collapse,
  Table,
  Tooltip,
  Space,
} from 'antd';
import type { CollapseProps, GetProp } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  BuildOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import {
  useListGoldImagesQuery,
  useCreateGoldImageMutation,
  useTriggerGoldBuildMutation,
  useScanGoldImageVersionMutation,
  useGetGoldImageScanResultsMutation,
  useGetHarborInstancesQuery,
  useSignGoldImageVersionMutation,
} from '../../store/api';
import { VulnerabilityBadge } from '../../components/VulnerabilityBadge';
import { SignatureBadge } from '../../components/SignatureBadge';
import { StatusChip } from '../../components/StatusChip';
import type { GoldImage, ImageVersion, HarborInstance } from '../../types';

export function GoldImagesPage() {
  const { message } = App.useApp();
  const { data: images = [], isLoading } = useListGoldImagesQuery();
  const { data: harborInstances = [] } = useGetHarborInstancesQuery();
  const [createImage] = useCreateGoldImageMutation();
  const [triggerBuild] = useTriggerGoldBuildMutation();
  const [scanVersion] = useScanGoldImageVersionMutation();
  const [getScanResults] = useGetGoldImageScanResultsMutation();
  const [signVersion] = useSignGoldImageVersionMutation();

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

  const [form, setForm] = useState({ name: '', os_family: '', description: '', dockerfile: '' });
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

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createImage(form).unwrap();
      setCreateOpen(false);
      setForm({ name: '', os_family: '', description: '', dockerfile: '' });
      message.success('Gold image created successfully');
    } catch {
      message.error('Failed to create gold image');
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
      message.success('Build triggered successfully');
    } catch {
      message.error('Failed to trigger build');
    } finally {
      setSubmitting(false);
    }
  };

  const handleScan = async () => {
    if (scanOpen === null) return;
    const { imageId, versionId } = scanOpen;
    setSubmitting(true);
    try {
      await scanVersion({
        imageId,
        versionId,
        harbor_instance_id: Number(scanForm.harbor_instance_id),
        project_name: scanForm.project_name,
        repository_name: scanForm.repository_name,
        artifact_digest: scanForm.artifact_digest,
      }).unwrap();
      setScanOpen(null);
      message.success('Scan triggered successfully');
      // Auto-fetch results after a short delay
      setTimeout(async () => {
        try {
          await getScanResults({
            imageId,
            versionId,
            harbor_instance_id: Number(scanForm.harbor_instance_id),
            project_name: scanForm.project_name,
            repository_name: scanForm.repository_name,
            artifact_digest: scanForm.artifact_digest,
          }).unwrap();
        } catch {
          // Results may not be ready yet — ignore
        }
      }, 5000);
    } catch {
      message.error('Scan trigger failed');
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
      message.success('Image signed successfully');
    } catch {
      message.error('Image signing failed');
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
          `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/gold-images/${imageId}/versions`,
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

  const versionColumns: ColumnsType<ImageVersion> = [
    {
      title: 'Tag',
      dataIndex: 'version_tag',
      key: 'version_tag',
    },
    {
      title: 'Arch',
      dataIndex: 'arch',
      key: 'arch',
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: ImageVersion) => (
        <StatusChip
          status={record.status_flag}
          statusText={record.status_text ?? undefined}
        />
      ),
    },
    {
      title: 'Security',
      key: 'security',
      render: (_: unknown, record: ImageVersion) => (
        <VulnerabilityBadge
          count={record.vulnerabilities}
          severity={record.vulnerability_severity}
          compact
        />
      ),
    },
    {
      title: 'Signature',
      key: 'signature',
      render: (_: unknown, record: ImageVersion) => (
        <SignatureBadge
          isSigned={record.is_signed}
          signature={record.cosign_signature}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: ImageVersion, _index: number) => {
        const image = (images as GoldImage[]).find((img) => img.id === record.gold_image_id);
        const imageName = image?.name ?? 'image';
        return (
          <Space size={4}>
            <Tooltip title="Sign image">
              <Button
                size="small"
                icon={<SafetyCertificateOutlined />}
                onClick={() => {
                  setSignForm({
                    image_reference: record.registry_url
                      ? `${record.registry_url}/${imageName}:${record.version_tag}`
                      : `${imageName}:${record.version_tag}`,
                    cosign_private_key: '',
                  });
                  setSignOpen({
                    imageId: record.gold_image_id ?? 0,
                    versionId: record.id,
                    registryUrl: record.registry_url,
                    versionTag: record.version_tag,
                  });
                }}
              />
            </Tooltip>
            <Tooltip title="Scan for vulnerabilities">
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => {
                  setScanForm({
                    harbor_instance_id: '',
                    project_name: '',
                    repository_name: '',
                    artifact_digest: record.sha256_digest || '',
                  });
                  setScanOpen({
                    imageId: record.gold_image_id ?? 0,
                    versionId: record.id,
                  });
                }}
              />
            </Tooltip>
          </Space>
        );
      },
    },
  ];

  // Build the Collapse items array for each image card
  const buildVersionCollapseItems = (imageId: number): CollapseProps['items'] => {
    const imageVersions = versions[imageId];
    const isLoadingVersions = loadingVersions.has(imageId);
    const label = `Versions (${imageVersions?.length ?? 0})`;

    return [
      {
        key: 'versions',
        label,
        children: isLoadingVersions ? (
          <Spin size="small" />
        ) : imageVersions?.length ? (
          <Table
            columns={versionColumns}
            dataSource={imageVersions}
            rowKey="id"
            size="small"
            pagination={false}
          />
        ) : (
          <Typography.Text type="secondary">No versions built yet.</Typography.Text>
        ),
      },
    ];
  };

  const harborOptions = (harborInstances as HarborInstance[]).map((h) => ({
    value: String(h.id),
    label: `${h.name} (${h.url})`,
  }));

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Gold Images
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Add Gold Image
        </Button>
      </Flex>

      {/* ── Card Grid ───────────────────────────────────────────────────────── */}
      {isLoading ? (
        <Flex justify="center" style={{ padding: 48 }}>
          <Spin size="large" />
        </Flex>
      ) : images.length === 0 ? (
        <Card>
          <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: '32px 0' }}>
            No gold images yet. Create one to get started.
          </Typography.Text>
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {(images as GoldImage[]).map((image) => (
            <Col key={image.id} xs={24} sm={12} lg={8}>
              <Card
                title={
                  <Flex justify="space-between" align="center">
                    <Typography.Text strong>{image.name}</Typography.Text>
                    <Tag color="blue">{image.os_family}</Tag>
                  </Flex>
                }
                actions={[
                  <Tooltip title="Trigger build" key="build">
                    <Button
                      type="text"
                      size="small"
                      icon={<BuildOutlined />}
                      onClick={() => {
                        setBuildForm({ version_tag: 'latest', arch: 'amd64' });
                        setBuildOpen(image.id);
                      }}
                    >
                      Build
                    </Button>
                  </Tooltip>,
                  <Tooltip title="Edit image" key="edit">
                    <Button type="text" size="small" icon={<EditOutlined />} />
                  </Tooltip>,
                  <Tooltip title="Delete image" key="delete">
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                  </Tooltip>,
                ]}
              >
                <Flex vertical gap={12}>
                  <Typography.Paragraph
                    type="secondary"
                    style={{ margin: 0 }}
                    ellipsis={{ rows: 2 }}
                  >
                    {image.description ?? 'No description'}
                  </Typography.Paragraph>

                  {image.dockerfile && (
                    <Typography.Paragraph
                      code
                      style={{
                        fontSize: '0.75rem',
                        maxHeight: 80,
                        overflow: 'hidden',
                        margin: 0,
                      }}
                    >
                      {image.dockerfile.slice(0, 200)}
                    </Typography.Paragraph>
                  )}

                  <Collapse
                    size="small"
                    ghost
                    items={buildVersionCollapseItems(image.id)}
                    activeKey={expandedImage === image.id ? ['versions'] : []}
                    onChange={() => toggleExpand(image.id)}
                  />
                </Flex>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* ── Create Modal ────────────────────────────────────────────────────── */}
      <Modal
        title="New Gold Image"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !form.name || !form.os_family }}
        okText="Create"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            placeholder="OS Family (ubuntu, alpine, debian...)"
            value={form.os_family}
            onChange={(e) => setForm({ ...form, os_family: e.target.value })}
            required
          />
          <Input
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <Input.TextArea
            placeholder="FROM ubuntu:22.04\nRUN apt-get update"
            rows={6}
            value={form.dockerfile}
            onChange={(e) => setForm({ ...form, dockerfile: e.target.value })}
          />
        </Space>
      </Modal>

      {/* ── Build Modal ─────────────────────────────────────────────────────── */}
      <Modal
        title="Trigger Build"
        open={buildOpen !== null}
        onOk={handleBuild}
        onCancel={() => setBuildOpen(null)}
        confirmLoading={submitting}
        okText="Build"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="Version Tag"
            value={buildForm.version_tag}
            onChange={(e) => setBuildForm({ ...buildForm, version_tag: e.target.value })}
          />
          <Input
            placeholder="Architecture (amd64, arm64, arm/v7)"
            value={buildForm.arch}
            onChange={(e) => setBuildForm({ ...buildForm, arch: e.target.value })}
          />
        </Space>
      </Modal>

      {/* ── Scan Modal ──────────────────────────────────────────────────────── */}
      <Modal
        title="Scan for Vulnerabilities"
        open={scanOpen !== null}
        onOk={handleScan}
        onCancel={() => setScanOpen(null)}
        confirmLoading={submitting}
        okButtonProps={{
          disabled:
            !scanForm.harbor_instance_id ||
            !scanForm.project_name ||
            !scanForm.repository_name ||
            !scanForm.artifact_digest,
        }}
        okText="Scan"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="Harbor Instance"
            style={{ width: '100%' }}
            value={scanForm.harbor_instance_id || undefined}
            onChange={(value) => setScanForm({ ...scanForm, harbor_instance_id: value })}
            options={harborOptions}
          />
          <Input
            placeholder="Project Name"
            value={scanForm.project_name}
            onChange={(e) => setScanForm({ ...scanForm, project_name: e.target.value })}
            required
          />
          <Input
            placeholder="Repository Name"
            value={scanForm.repository_name}
            onChange={(e) => setScanForm({ ...scanForm, repository_name: e.target.value })}
            required
          />
          <Input
            placeholder="Artifact Digest (sha256:abc123...)"
            value={scanForm.artifact_digest}
            onChange={(e) => setScanForm({ ...scanForm, artifact_digest: e.target.value })}
            required
          />
        </Space>
      </Modal>

      {/* ── Sign Modal ──────────────────────────────────────────────────────── */}
      <Modal
        title="Sign Image with Cosign"
        open={signOpen !== null}
        onOk={handleSign}
        onCancel={() => setSignOpen(null)}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !signForm.image_reference || !signForm.cosign_private_key }}
        okText="Sign"
        cancelText="Cancel"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="registry.example.com/project/image:tag"
            value={signForm.image_reference}
            onChange={(e) => setSignForm({ ...signForm, image_reference: e.target.value })}
            required
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Full image reference including registry and tag
          </Typography.Text>
          <Input.TextArea
            placeholder="-----BEGIN ENCRYPTED COSIGN PRIVATE KEY-----"
            rows={6}
            value={signForm.cosign_private_key}
            onChange={(e) => setSignForm({ ...signForm, cosign_private_key: e.target.value })}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            PEM-encoded cosign private key. Not stored in the database.
          </Typography.Text>
        </Space>
      </Modal>
    </Flex>
  );
}
