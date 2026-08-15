import { Card, Col, Flex, Row, Spin, Typography } from 'antd';
import { GithubOutlined, SwapOutlined, BlockOutlined, AppstoreOutlined } from '@ant-design/icons';
import {
  useListProjectsQuery,
  useGetMirrorsQuery,
  useListGoldImagesQuery,
  useListAppImagesQuery,
} from '../../store/api';
import { StatusChip } from '../../components/StatusChip';
import { Mirror, STATUS_FLAG } from '../../types';

const { Title, Text } = Typography;

function StatCard({
  title,
  count,
  icon,
  isLoading,
}: {
  title: string;
  count: number;
  icon: React.ReactNode;
  isLoading: boolean;
}) {
  return (
    <Card>
      <Flex align="center" justify="space-between">
        <Flex vertical>
          <Text type="secondary">{title}</Text>
          <Title level={4} style={{ margin: 0, fontWeight: 'bold' }}>
            {isLoading ? <Spin size="small" /> : count}
          </Title>
        </Flex>
        <Flex style={{ color: 'var(--ant-color-primary)', opacity: 0.7 }}>{icon}</Flex>
      </Flex>
    </Card>
  );
}

export function DashboardPage() {
  const { data: projects = [], isLoading: loadingProjects } = useListProjectsQuery();
  const { data: mirrors = [], isLoading: loadingMirrors } = useGetMirrorsQuery({ limit: 500 });
  const { data: goldImages = [], isLoading: loadingGold } = useListGoldImagesQuery();
  const { data: appImages = [], isLoading: loadingApp } = useListAppImagesQuery();

  const staleMirrors = (mirrors as Mirror[]).filter((m) => m.status_flag === STATUS_FLAG.WARNING);
  const failedMirrors = (mirrors as Mirror[]).filter((m) => m.status_flag === STATUS_FLAG.FAILED);

  return (
    <Flex vertical>
      <Title level={4} style={{ fontWeight: 'bold', marginBottom: 24 }}>
        Dashboard
      </Title>

      <Row gutter={[24, 24]} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            title="GitHub Projects"
            count={projects.length}
            icon={<GithubOutlined style={{ fontSize: 40 }} />}
            isLoading={loadingProjects}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            title="GitLab Mirrors"
            count={mirrors.length}
            icon={<SwapOutlined style={{ fontSize: 40 }} />}
            isLoading={loadingMirrors}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            title="Gold Images"
            count={goldImages.length}
            icon={<BlockOutlined style={{ fontSize: 40 }} />}
            isLoading={loadingGold}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            title="App Images"
            count={appImages.length}
            icon={<AppstoreOutlined style={{ fontSize: 40 }} />}
            isLoading={loadingApp}
          />
        </Col>
      </Row>

      {(staleMirrors.length > 0 || failedMirrors.length > 0) && (
        <Card style={{ marginBottom: 24 }}>
          <Title level={5} style={{ marginBottom: 16 }}>
            Attention Required
          </Title>
          {failedMirrors.length > 0 && (
            <Flex style={{ marginBottom: 8 }}>
              <Text type="danger">{failedMirrors.length} mirror(s) failed last sync</Text>
            </Flex>
          )}
          {staleMirrors.length > 0 && (
            <Flex>
              <Text type="warning">{staleMirrors.length} mirror(s) are stale</Text>
            </Flex>
          )}
        </Card>
      )}

      <Card>
        <Title level={5} style={{ marginBottom: 16 }}>
          Recent Mirrors Status
        </Title>
        {loadingMirrors ? (
          <Spin />
        ) : (
          <Flex vertical gap="small">
            {(mirrors as Mirror[]).slice(0, 5).map((mirror) => (
              <Flex key={mirror.id} align="center" justify="space-between">
                <Text>{mirror.target_gitlab_name ?? mirror.target_path}</Text>
                <StatusChip statusFlag={mirror.status_flag} statusText={mirror.status_text} />
              </Flex>
            ))}
            {mirrors.length === 0 && <Text type="secondary">No mirrors configured yet</Text>}
          </Flex>
        )}
      </Card>
    </Flex>
  );
}
