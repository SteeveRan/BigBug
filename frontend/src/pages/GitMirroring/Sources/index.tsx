/**
 * @file index.tsx
 * @description Страница Sources — объединяет Repositories и Groups вкладки
 * @dependencies antd, react-router
 */

import { useState, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router';
import { Tabs, Typography, Flex, Skeleton, Breadcrumb } from 'antd';
import { BranchesOutlined, ApartmentOutlined } from '@ant-design/icons';
import { RepositoriesTab } from './RepositoriesTab';
import { GroupsTab } from './GroupsTab';

const tabItems = [
  {
    key: 'repositories',
    label: (
      <span>
        <BranchesOutlined style={{ marginRight: 6 }} />
        Repositories
      </span>
    ),
    children: <RepositoriesTab />,
  },
  {
    key: 'groups',
    label: (
      <span>
        <ApartmentOutlined style={{ marginRight: 6 }} />
        Groups
      </span>
    ),
    children: <GroupsTab />,
  },
];

export function SourcesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeKey = searchParams.get('tab') || 'repositories';
  const [loading, setLoading] = useState(false);

  const handleTabChange = useCallback(
    (key: string) => {
      setLoading(true);
      setSearchParams({ tab: key }, { replace: true });
      // Simulate tab switch loading for UX
      setTimeout(() => setLoading(false), 100);
    },
    [setSearchParams]
  );

  return (
    <Flex vertical gap={16}>
      <Breadcrumb
        items={[
          { title: <Link to="/git-mirroring/dashboard">Git Mirroring</Link> },
          { title: 'Sources' },
        ]}
      />
      <Typography.Title level={4} style={{ margin: 0 }}>
        Sources
      </Typography.Title>
      <Typography.Text type="secondary">
        Manage source repositories and their parent groups (GitHub organizations, GitLab groups).
        Repositories are discovered automatically when you import a group, or manually for Generic
        Git providers.
      </Typography.Text>

      {loading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : (
        <Tabs activeKey={activeKey} onChange={handleTabChange} items={tabItems} />
      )}
    </Flex>
  );
}

export default SourcesPage;
