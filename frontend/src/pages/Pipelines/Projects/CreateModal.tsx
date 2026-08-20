/**
 * @file Pipelines/Projects/CreateModal.tsx
 * @description Create or Import a GitLab project modal. Supports both actions:
 *              create-in-GitLab (POST /gitlab-projects) and import-existing
 *              (POST /gitlab-projects/import).
 * @dependencies antd, RTK Query, types
 * @relatedFiles ./index.tsx
 */

import { useEffect, useState } from 'react';
import { Alert, App, Form, Input, Modal, Select, Switch } from 'antd';
import {
  useCreateGitlabProjectMutation,
  useGetProvidersQuery,
  useImportGitlabProjectMutation,
} from '../../../store/api';
import type { GitlabProjectCreate, GitlabProjectImport, GitlabProjectType } from '../../../types';

interface CreateProjectModalProps {
  open: boolean;
  onClose: () => void;
  projectType?: GitlabProjectType;
  hasWrite: boolean;
}

type Mode = 'create' | 'import';

interface FormValues {
  name: string;
  path: string;
  namespace_path: string;
  project_type: GitlabProjectType;
  provider_id: number;
  gitlab_visibility: string;
  default_branch: string;
  description?: string;
  full_path?: string;
  initialize_with_readme: boolean;
}

export function CreateProjectModal({
  open,
  onClose,
  projectType,
  hasWrite,
}: CreateProjectModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<FormValues>();
  const [mode, setMode] = useState<Mode>('create');

  const { data: providers = [] } = useGetProvidersQuery({ subtype: 'gitlab' });
  const [createProject, { isLoading: isCreating }] = useCreateGitlabProjectMutation();
  const [importProject, { isLoading: isImporting }] = useImportGitlabProjectMutation();

  const isLoading = isCreating || isImporting;

  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue({
        project_type: projectType ?? 'components',
        gitlab_visibility: 'private',
        default_branch: 'main',
        initialize_with_readme: true,
      });
      setMode('create');
    }
  }, [open, projectType, form]);

  const handleSubmit = async (values: FormValues) => {
    try {
      if (mode === 'create') {
        const data: GitlabProjectCreate = {
          name: values.name,
          path: values.path,
          namespace_path: values.namespace_path,
          project_type: values.project_type,
          provider_id: values.provider_id,
          gitlab_visibility: values.gitlab_visibility,
          default_branch: values.default_branch,
          description: values.description || null,
          initialize_with_readme: values.initialize_with_readme,
        };
        await createProject(data).unwrap();
        message.success('GitLab project created');
      } else {
        const data: GitlabProjectImport = {
          provider_id: values.provider_id,
          full_path: values.full_path ?? '',
          project_type: values.project_type,
        };
        await importProject(data).unwrap();
        message.success('GitLab project imported');
      }
      onClose();
    } catch (err) {
      const detail = (err as { data?: { detail?: string } })?.data?.detail;
      message.error(detail ?? 'Operation failed');
    }
  };

  const providerOptions = providers.map((p) => ({
    label: `${p.label}${p.base_url ? ` (${p.base_url})` : ''}`,
    value: p.id,
  }));

  return (
    <Modal
      title={mode === 'create' ? 'Create GitLab Project' : 'Import GitLab Project'}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={isLoading}
      okText={mode === 'create' ? 'Create' : 'Import'}
      cancelText="Cancel"
      destroyOnHidden
      width={560}
      okButtonProps={{ disabled: !hasWrite }}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item label="Mode">
          <Select
            value={mode}
            onChange={(v) => setMode(v as Mode)}
            options={[
              { label: 'Create in GitLab', value: 'create' },
              { label: 'Import existing', value: 'import' },
            ]}
          />
        </Form.Item>

        <Form.Item
          name="provider_id"
          label="GitLab Provider"
          rules={[{ required: true, message: 'Provider is required' }]}
        >
          <Select placeholder="Select GitLab provider" options={providerOptions} />
        </Form.Item>

        <Form.Item
          name="project_type"
          label="Project Type"
          rules={[{ required: true, message: 'Project type is required' }]}
        >
          <Select
            options={[
              { label: 'Components', value: 'components' },
              { label: 'Pipelines', value: 'pipelines' },
            ]}
          />
        </Form.Item>

        {mode === 'import' ? (
          <Form.Item
            name="full_path"
            label="Full Path"
            rules={[{ required: true, message: 'Full path is required' }]}
          >
            <Input placeholder="namespace/project" />
          </Form.Item>
        ) : (
          <>
            <Form.Item
              name="name"
              label="Name"
              rules={[{ required: true, message: 'Name is required' }]}
            >
              <Input placeholder="Display name" />
            </Form.Item>
            <Form.Item
              name="path"
              label="Path"
              rules={[{ required: true, message: 'Path is required' }]}
            >
              <Input placeholder="project-slug" />
            </Form.Item>
            <Form.Item
              name="namespace_path"
              label="Namespace Path"
              rules={[{ required: true, message: 'Namespace path is required' }]}
            >
              <Input placeholder="group or username" />
            </Form.Item>
            <Form.Item name="gitlab_visibility" label="GitLab Visibility">
              <Select
                options={[
                  { label: 'Private', value: 'private' },
                  { label: 'Internal', value: 'internal' },
                  { label: 'Public', value: 'public' },
                ]}
              />
            </Form.Item>
            <Form.Item name="default_branch" label="Default Branch">
              <Input placeholder="main" />
            </Form.Item>
            <Form.Item name="description" label="Description">
              <Input.TextArea rows={2} placeholder="Optional description" />
            </Form.Item>
            <Form.Item
              name="initialize_with_readme"
              label="Initialize with README"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </>
        )}
      </Form>

      {!hasWrite && (
        <Alert
          type="warning"
          title="You do not have permission to create projects"
          showIcon
          style={{ marginTop: 12 }}
        />
      )}
    </Modal>
  );
}

export default CreateProjectModal;
