/**
 * @file DockerImageCompare.tsx
 * @description Страница сравнения тегов между двумя Docker Image источниками.
 *              Селекторы источников, карточка Summary, таблица сравнения тегов.
 * @dependencies antd, @ant-design/icons, Redux store (RTK Query), react-router
 */
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Card,
  Typography,
  Button,
  Select,
  Table,
  Flex,
  Spin,
  Badge,
  App,
  Statistic,
  Row,
  Col,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ArrowLeftOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import {
  useListDockerImagesQuery,
  useCompareDockerImagesQuery,
} from '../../store/api';
import type {
  DockerImageSource,
  DockerImageTagCompareItem,
  DockerImageCompareResponse,
} from '../../types';

/**
 * Форматирует размер в байтах в человекочитаемую строку.
 */
function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIdx = 0;
  while (size >= 1024 && unitIdx < units.length - 1) {
    size /= 1024;
    unitIdx++;
  }
  return `${size.toFixed(1)} ${units[unitIdx]}`;
}

/**
 * Возвращает цвет Badge и текст статуса сравнения для тега.
 */
function getTagStatus(tag: DockerImageTagCompareItem): {
  color: 'green' | 'orange' | 'blue' | 'purple';
  text: string;
} {
  if (tag.match === true) return { color: 'green', text: 'Matching' };
  if (tag.match === false) return { color: 'orange', text: 'Differing' };
  if (tag.digest_a && !tag.digest_b) return { color: 'blue', text: 'Only in A' };
  if (tag.digest_b && !tag.digest_a) return { color: 'purple', text: 'Only in B' };
  return { color: 'orange', text: 'Differing' };
}

export function DockerImageComparePage() {
  const navigate = useNavigate();
  const { message } = App.useApp();

  // Список всех Docker Image источников для селекторов
  const { data: sources = [], isLoading: sourcesLoading } = useListDockerImagesQuery();

  // Выбранные источники
  const [sourceAId, setSourceAId] = useState<number | null>(null);
  const [sourceBId, setSourceBId] = useState<number | null>(null);

  // Запрос сравнения (skip если не выбраны оба)
  const {
    data: compareData,
    isLoading: compareLoading,
    isFetching: compareFetching,
  } = useCompareDockerImagesQuery(
    { sourceAId: sourceAId!, sourceBId: sourceBId! },
    { skip: sourceAId === null || sourceBId === null },
  );

  const canCompare = sourceAId !== null && sourceBId !== null && sourceAId !== sourceBId;

  const handleCompare = () => {
    if (!canCompare) {
      message.warning('Please select two different sources to compare');
      return;
    }
    // RTK Query automatically refetches when sourceAId/sourceBId change,
    // but if user clicks Compare after changing selection, we ensure query runs
  };

  // Опции для Select
  const sourceOptions = useMemo(
    () =>
      (sources as DockerImageSource[]).map((s) => ({
        value: s.id,
        label: `${s.name} (${s.registry_url})`,
      })),
    [sources],
  );

  // Колонки таблицы сравнения
  const columns: ColumnsType<DockerImageTagCompareItem> = [
    {
      title: 'Tag',
      dataIndex: 'tag',
      key: 'tag',
      render: (val: string) => (
        <Typography.Text code style={{ fontSize: '0.8rem' }}>
          {val}
        </Typography.Text>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      width: 140,
      render: (_: unknown, record: DockerImageTagCompareItem) => {
        const { color, text } = getTagStatus(record);
        return <Badge color={color} text={text} />;
      },
    },
    {
      title: 'Digest A',
      dataIndex: 'digest_a',
      key: 'digest_a',
      render: (val: string | null) => (
        <Typography.Text
          code
          type={val ? undefined : 'secondary'}
          style={{
            fontSize: '0.75rem',
            wordBreak: 'break-all',
          }}
        >
          {val ? val.slice(0, 18) : '—'}
        </Typography.Text>
      ),
    },
    {
      title: 'Digest B',
      dataIndex: 'digest_b',
      key: 'digest_b',
      render: (val: string | null) => (
        <Typography.Text
          code
          type={val ? undefined : 'secondary'}
          style={{
            fontSize: '0.75rem',
            wordBreak: 'break-all',
          }}
        >
          {val ? val.slice(0, 18) : '—'}
        </Typography.Text>
      ),
    },
    {
      title: 'Size A',
      dataIndex: 'size_bytes_a',
      key: 'size_bytes_a',
      render: (val: number | null) => formatBytes(val),
    },
    {
      title: 'Size B',
      dataIndex: 'size_bytes_b',
      key: 'size_bytes_b',
      render: (val: number | null) => formatBytes(val),
    },
  ];

  const summary = (compareData as DockerImageCompareResponse | undefined)?.summary;
  const tags = (compareData as DockerImageCompareResponse | undefined)?.tags ?? [];
  const sourceA = (compareData as DockerImageCompareResponse | undefined)?.source_a;
  const sourceB = (compareData as DockerImageCompareResponse | undefined)?.source_b;

  const loading = compareLoading || compareFetching;

  return (
    <Flex vertical gap={16}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <Flex align="center" gap={12} wrap="wrap">
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/mirroring/docker-images')}
        >
          Back
        </Button>
        <Typography.Title level={4} style={{ margin: 0, flex: 1 }}>
          Docker Image Comparison
        </Typography.Title>
      </Flex>

      {/* ── Source Selectors Card ───────────────────────────────────────────── */}
      <Card>
        <Flex gap={16} align="center" wrap="wrap">
          <Flex vertical style={{ flex: 1, minWidth: 250 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>
              Source A
            </Typography.Text>
            <Select
              showSearch
              placeholder="Select source A…"
              loading={sourcesLoading}
              value={sourceAId}
              onChange={(val) => setSourceAId(val)}
              options={sourceOptions}
              filterOption={(input, option) =>
                (option?.label as string).toLowerCase().includes(input.toLowerCase())
              }
              style={{ width: '100%' }}
            />
          </Flex>

          <SwapOutlined
            style={{
              fontSize: 20,
              color: '#8c8c8c',
              marginTop: 18,
            }}
          />

          <Flex vertical style={{ flex: 1, minWidth: 250 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>
              Source B
            </Typography.Text>
            <Select
              showSearch
              placeholder="Select source B…"
              loading={sourcesLoading}
              value={sourceBId}
              onChange={(val) => setSourceBId(val)}
              options={sourceOptions}
              filterOption={(input, option) =>
                (option?.label as string).toLowerCase().includes(input.toLowerCase())
              }
              style={{ width: '100%' }}
            />
          </Flex>

          <Button
            type="primary"
            icon={<SwapOutlined />}
            onClick={handleCompare}
            disabled={!canCompare}
            loading={loading}
            style={{ marginTop: 18 }}
          >
            Compare
          </Button>
        </Flex>
      </Card>

      {/* ── Loading State ───────────────────────────────────────────────────── */}
      {loading && (
        <Flex justify="center" style={{ padding: 48 }}>
          <Spin size="large" />
        </Flex>
      )}

      {/* ── Results (shown only when comparison data is available) ──────────── */}
      {!loading && compareData && (
        <>
          {/* ── Source Info ──────────────────────────────────────────────── */}
          <Flex gap={16} wrap="wrap">
            <Card
              title={`Source A: ${sourceA?.name ?? '—'}`}
              style={{ flex: '1 1 300px', minWidth: 280 }}
            >
              <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                {sourceA?.registry_url ?? '—'}
              </Typography.Text>
            </Card>
            <Card
              title={`Source B: ${sourceB?.name ?? '—'}`}
              style={{ flex: '1 1 300px', minWidth: 280 }}
            >
              <Typography.Text code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                {sourceB?.registry_url ?? '—'}
              </Typography.Text>
            </Card>
          </Flex>

          {/* ── Summary Statistics Card ──────────────────────────────────── */}
          {summary && (
            <Card title="Comparison Summary">
              <Row gutter={[24, 16]}>
                <Col xs={12} sm={8} md={4}>
                  <Statistic title="Total Tags" value={summary.total_tags} />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title="Matching"
                    value={summary.matching_tags}
                    valueStyle={{ color: '#52c41a' }}
                    suffix={
                      summary.total_tags > 0
                        ? `(${((summary.matching_tags / summary.total_tags) * 100).toFixed(0)}%)`
                        : undefined
                    }
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title="Differing"
                    value={summary.differing_tags}
                    valueStyle={{ color: '#fa8c16' }}
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title="Only in A"
                    value={summary.only_in_a}
                    valueStyle={{ color: '#1677ff' }}
                  />
                </Col>
                <Col xs={12} sm={8} md={4}>
                  <Statistic
                    title="Only in B"
                    value={summary.only_in_b}
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Col>
              </Row>
            </Card>
          )}

          {/* ── Tags Comparison Table ────────────────────────────────────── */}
          <Card title={`Tag Comparison (${tags.length} tags)`}>
            <Table
              columns={columns}
              dataSource={tags as DockerImageTagCompareItem[]}
              rowKey="tag"
              size="small"
              pagination={tags.length > 50 ? { pageSize: 50 } : false}
              locale={{ emptyText: 'No tags to compare' }}
            />
          </Card>
        </>
      )}

      {/* ── Empty state (no comparison run yet) ─────────────────────────────── */}
      {!loading && !compareData && (
        <Flex justify="center" style={{ padding: 48 }}>
          <Typography.Text type="secondary">
            Select two sources and click «Compare» to see the results.
          </Typography.Text>
        </Flex>
      )}
    </Flex>
  );
}
