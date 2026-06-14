import { Typography, Card, Empty, Flex, Breadcrumb } from 'antd';
import { Link } from 'react-router';

const DashboardPage = () => (
  <Flex vertical gap={16}>
    <Breadcrumb
      items={[
        { title: <Link to="/git-mirroring/dashboard">Git Mirroring</Link> },
        { title: 'Dashboard' },
      ]}
    />
    <Card>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Git Mirroring Dashboard
      </Typography.Title>
      <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Overview of mirroring health, sync activity, and system status across all providers, sync
        groups, and target instances.
      </Typography.Text>
      <Empty description="Detailed dashboard widgets will be available in a future stage." />
    </Card>
  </Flex>
);

export default DashboardPage;
