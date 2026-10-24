/**
 * @file Admin/TrustStores/index.tsx
 * @description Trust Stores management page (`/admin/trust-stores`, ADR-0037):
 *              store CRUD, certificate list with per-cert delete, add PEM form
 *              (textarea + file upload), usage shown in delete confirm.
 * @dependencies antd, RTK Query, PermissionGate
 * @relatedFiles ../../../store/api.ts, ../../../types/index.ts
 */

import { useRef, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Empty,
  Flex,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Typography,
  Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, DeleteOutlined, UploadOutlined } from '@ant-design/icons';
import {
  useGetTrustStoresQuery,
  useCreateTrustStoreMutation,
  useUpdateTrustStoreMutation,
  useDeleteTrustStoreMutation,
  useGetTrustStoreUsageQuery,
  useAddTrustStoreCertificatesMutation,
  useDeleteTrustStoreCertificateMutation,
} from '../../../store/api';
import type { TrustStore, TrustStoreUsage } from '../../../types';
import { PermissionGate } from '../../../components/PermissionGate';

function errorDetail(err: unknown): string | undefined {
  return (err as { data?: { detail?: string } })?.data?.detail;
}

interface StoreFormValues {
  name: string;
  description?: string;
}

function StoreModal({
  open,
  store,
  onClose,
}: {
  open: boolean;
  store?: TrustStore;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<StoreFormValues>();
  const isEdit = !!store;
  const [createTrustStore, { isLoading: isCreating }] = useCreateTrustStoreMutation();
  const [updateTrustStore, { isLoading: isUpdating }] = useUpdateTrustStoreMutation();
  const isLoading = isCreating || isUpdating;

  const handleSubmit = async (values: StoreFormValues) => {
    try {
      if (isEdit && store) {
        await updateTrustStore({ id: store.id, data: values }).unwrap();
        message.success('Trust store updated');
      } else {
        await createTrustStore(values).unwrap();
        message.success('Trust store created');
      }
      onClose();
    } catch (err) {
      message.error(errorDetail(err) ?? 'Failed to save trust store');
    }
  };

  return (
    <Modal
      title={isEdit ? `Edit trust store: ${store?.name}` : 'Create trust store'}
      open={open}
      onCancel={onClose}
      destroyOnHidden
      footer={[
        <Button key="cancel" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>,
        <Button key="save" type="primary" loading={isLoading} onClick={() => form.submit()}>
          {isEdit ? 'Save' : 'Create'}
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{ name: store?.name, description: store?.description ?? undefined }}
      >
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. corporate-ca" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

interface AddCertsFormValues {
  name: string;
  pem: string;
}

function AddCertificatesModal({ store, onClose }: { store?: TrustStore; onClose: () => void }) {
  const { message } = App.useApp();
  const [form] = Form.useForm<AddCertsFormValues>();
  const [addCertificates, { isLoading }] = useAddTrustStoreCertificatesMutation();

  // antd Upload beforeUpload returning false keeps the file local — we only
  // read its text into the textarea, never upload it.
  const readFile = async (file: File) => {
    const text = await file.text();
    form.setFieldsValue({ pem: text });
    return false;
  };

  const handleSubmit = async (values: AddCertsFormValues) => {
    if (!store) return;
    try {
      const added = await addCertificates({
        id: store.id,
        data: { name: values.name, pem: values.pem },
      }).unwrap();
      message.success(`Added ${added.length} certificate(s)`);
      onClose();
    } catch (err) {
      message.error(errorDetail(err) ?? 'Failed to add certificates');
    }
  };

  return (
    <Modal
      title={`Add certificates to ${store?.name ?? ''}`}
      open={!!store}
      onCancel={onClose}
      destroyOnHidden
      footer={[
        <Button key="cancel" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>,
        <Button key="add" type="primary" loading={isLoading} onClick={() => form.submit()}>
          Add
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. corporate-root (chain blocks get -1, -2 suffixes)" />
        </Form.Item>
        <Form.Item label="PEM">
          <Space.Compact block direction="vertical">
            <Form.Item name="pem" noStyle rules={[{ required: true }]}>
              <Input.TextArea
                rows={10}
                placeholder={'-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----'}
              />
            </Form.Item>
            <Upload
              accept=".pem,.crt"
              multiple
              beforeUpload={readFile}
              showUploadList={false}
              maxCount={1}
            >
              <Button icon={<UploadOutlined />}>Load .pem/.crt file</Button>
            </Upload>
          </Space.Compact>
        </Form.Item>
      </Form>
    </Modal>
  );
}

function DeleteStoreButton({ store }: { store: TrustStore }) {
  const { message, modal } = App.useApp();
  const [deleteTrustStore] = useDeleteTrustStoreMutation();
  const [getUsage] = useGetTrustStoreUsageQuery.useLazyQuery();
  const usageRef = useRef<TrustStoreUsage | null>(null);

  const handleDelete = async () => {
    try {
      usageRef.current = await getUsage(store.id).unwrap();
    } catch {
      usageRef.current = null;
    }
    const usage = usageRef.current;
    modal.confirm({
      title: `Delete trust store "${store.name}"?`,
      content:
        usage && usage.providers.length > 0 ? (
          <div>
            <Typography.Text type="warning">
              In use by {usage.providers.length} provider(s):
            </Typography.Text>
            <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
              {usage.providers.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        ) : (
          'This action cannot be undone.'
        ),
      okButtonProps: { danger: true },
      okText: 'Delete',
      onOk: async () => {
        try {
          await deleteTrustStore(store.id).unwrap();
          message.success(`Trust store "${store.name}" deleted`);
        } catch (err) {
          // 409 with provider list from the backend
          message.error(errorDetail(err) ?? 'Failed to delete trust store');
        }
      },
    });
  };

  return (
    <Button
      size="small"
      type="text"
      danger
      icon={<DeleteOutlined />}
      aria-label={`Delete trust store ${store.name}`}
      onClick={handleDelete}
    />
  );
}

export function AdminTrustStores() {
  const { message } = App.useApp();
  const { data: stores = [], isLoading, isError } = useGetTrustStoresQuery();
  const [deleteCertificate] = useDeleteTrustStoreCertificateMutation();

  const [storeModalOpen, setStoreModalOpen] = useState(false);
  const [editing, setEditing] = useState<TrustStore | undefined>(undefined);
  const [addTarget, setAddTarget] = useState<TrustStore | undefined>(undefined);

  const handleDeleteCert = async (storeId: number, certId: number, certName: string) => {
    try {
      await deleteCertificate({ storeId, certificateId: certId }).unwrap();
      message.success(`Certificate "${certName}" deleted`);
    } catch (err) {
      message.error(errorDetail(err) ?? 'Failed to delete certificate');
    }
  };

  const columns: ColumnsType<TrustStore> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Flex vertical>
          <Typography.Text strong>{name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.description ?? '—'}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Certificates',
      key: 'certificates',
      width: 140,
      render: (_: unknown, record) => (
        <Typography.Text>{record.certificates.length} CA</Typography.Text>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => <Typography.Text>{v}</Typography.Text>,
    },
    {
      title: 'Actions',
      key: 'actions',
      align: 'right',
      width: 200,
      render: (_: unknown, record) => (
        <Space size={4}>
          <Button size="small" type="text" onClick={() => setAddTarget(record)}>
            Add certs
          </Button>
          <PermissionGate permission="trust_stores:write">
            <Button
              size="small"
              type="text"
              onClick={() => {
                setEditing(record);
                setStoreModalOpen(true);
              }}
            >
              Edit
            </Button>
            <DeleteStoreButton store={record} />
          </PermissionGate>
        </Space>
      ),
    },
  ];

  const expandedRowRender = (store: TrustStore) => (
    <Table
      columns={[
        { title: 'Name', dataIndex: 'name', key: 'name' },
        {
          title: 'Fingerprint (SHA-256)',
          dataIndex: 'fingerprint',
          key: 'fingerprint',
          render: (fp: string) => (
            <Typography.Text code copyable={{ text: fp }} style={{ fontSize: 12 }}>
              {fp.slice(0, 16)}…
            </Typography.Text>
          ),
        },
        { title: 'Created', dataIndex: 'created_at', key: 'created_at' },
        {
          title: '',
          key: 'actions',
          align: 'right',
          render: (_: unknown, cert) => (
            <PermissionGate permission="trust_stores:write">
              <Popconfirm
                title={`Delete certificate "${cert.name}"?`}
                onConfirm={() => handleDeleteCert(store.id, cert.id, cert.name)}
              >
                <Button
                  size="small"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  aria-label={`Delete certificate ${cert.name}`}
                />
              </Popconfirm>
            </PermissionGate>
          ),
        },
      ]}
      dataSource={store.certificates}
      rowKey="id"
      pagination={false}
      locale={{ emptyText: <Empty description="No certificates" /> }}
    />
  );

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap="wrap" gap={8}>
        <Flex vertical gap={4}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Trust Stores
          </Typography.Title>
          <Typography.Text type="secondary">
            Named CA bundles that providers can reference for TLS verification.
          </Typography.Text>
        </Flex>
        <PermissionGate permission="trust_stores:write">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(undefined);
              setStoreModalOpen(true);
            }}
          >
            Create trust store
          </Button>
        </PermissionGate>
      </Flex>

      {isLoading ? (
        <Flex justify="center" style={{ padding: '40px 0' }}>
          <Spin size="large" />
        </Flex>
      ) : isError ? (
        <Alert title="Failed to load trust stores" type="error" showIcon />
      ) : (
        <Card>
          <Table
            columns={columns}
            dataSource={stores as TrustStore[]}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            expandable={{ expandedRowRender }}
            locale={{ emptyText: <Empty description="No trust stores configured" /> }}
          />
        </Card>
      )}

      <StoreModal
        open={storeModalOpen}
        store={editing}
        onClose={() => {
          setStoreModalOpen(false);
          setEditing(undefined);
        }}
      />
      <AddCertificatesModal store={addTarget} onClose={() => setAddTarget(undefined)} />
    </Flex>
  );
}

export default AdminTrustStores;
