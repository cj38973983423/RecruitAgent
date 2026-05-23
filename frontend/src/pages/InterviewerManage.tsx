import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Typography, Table, Tag, Space, Button, Modal,
  Input, Form, Select, message, Popconfirm, Tooltip, Row, Col,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  StopOutlined, CheckCircleOutlined, ReloadOutlined,
  SearchOutlined, MailOutlined, PhoneOutlined,
} from '@ant-design/icons';
import {
  listInterviewers, createInterviewer, updateInterviewer,
  deleteInterviewer, toggleInterviewerStatus,
} from '../api';
import { EmptyGuide, stepIcons } from '../components/EmptyGuide';
import type { Interviewer } from '../types';

const { Title, Text } = Typography;
const { TextArea } = Input;

const InterviewerManage: React.FC = () => {
  const [data, setData] = useState<Interviewer[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Interviewer | null>(null);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (keyword) params.keyword = keyword;
      const res = await listInterviewers(params);
      setData(Array.isArray(res) ? res : []);
    } catch (err) {
      message.error('加载面试官列表失败');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, keyword]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpen = (record?: any) => {
    if (record) {
      setEditing(record);
      // skills 可能是数组（后端新格式），转成逗号字符串供输入框显示
      const formValues = { ...record };
      if (Array.isArray(formValues.skills)) {
        formValues.skills = formValues.skills.join(', ');
      }
      form.setFieldsValue(formValues);
    } else {
      setEditing(null);
      form.resetFields();
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      // skills 是逗号分隔的字符串，转成数组提交
      if (typeof values.skills === 'string') {
        values.skills = values.skills.split(/[,，、]/).map((s: string) => s.trim()).filter(Boolean);
      }
      if (editing) {
        await updateInterviewer(editing.id, values);
        message.success('✅ 面试官信息已更新');
      } else {
        await createInterviewer(values);
        message.success('✅ 面试官已添加');
      }
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      if (err?.errorFields) return; // form validation error
      message.error('保存失败');
    }
  };

  const handleDelete = async (id: number, name: string) => {
    try {
      await deleteInterviewer(id);
      message.success(`已删除「${name}」`);
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleToggleStatus = async (id: number) => {
    try {
      const res = await toggleInterviewerStatus(id);
      message.success(`状态已切换为: ${res.status}`);
      fetchData();
    } catch {
      message.error('状态切换失败');
    }
  };

  const columns = [
    {
      title: '姓名', dataIndex: 'name', key: 'name', width: 120,
      render: (n: string, r: any) => (
        <Space>
          <Text strong>{n}</Text>
          <Tag color={r.status === 'active' ? 'green' : 'red'} style={{ fontSize: 11 }}>
            {r.status === 'active' ? '在职' : '停用'}
          </Tag>
        </Space>
      ),
    },
    {
      title: '职位', dataIndex: 'position', key: 'position', width: 150,
      render: (v: string) => v || '-',
    },
    {
      title: '部门', dataIndex: 'department', key: 'department', width: 120,
      render: (v: string) => v ? <Tag>{v}</Tag> : '-',
    },
    {
      title: '联系方式', key: 'contact', width: 200,
      render: (_: any, r: any) => (
        <Space direction="vertical" size={2}>
          {r.email && <Text type="secondary" style={{ fontSize: 12 }}>
            <MailOutlined /> {r.email}
          </Text>}
          {r.phone && <Text type="secondary" style={{ fontSize: 12 }}>
            <PhoneOutlined /> {r.phone}
          </Text>}
        </Space>
      ),
    },
    {
      title: '擅长领域', dataIndex: 'skills', key: 'skills', width: 200,
      render: (v: string | string[]) => {
        if (!v) return '-';
        const skills = Array.isArray(v)
          ? v
          : v.split(/[,，、]/).filter(Boolean);
        return (
          <Space wrap size={4}>
            {skills.map((s, i) => <Tag key={i} color="blue" style={{ fontSize: 11 }}>{s.trim()}</Tag>)}
          </Space>
        );
      },
    },
    {
      title: '面试次数', dataIndex: 'interview_count', key: 'count', width: 80,
      render: (v: number) => <Text strong style={{ color: '#3b82f6' }}>{v ?? 0} 次</Text>,
    },
    {
      title: '评分', dataIndex: 'rating', key: 'rating', width: 80,
      render: (v: number | null) => {
        if (v == null) return '-';
        const color = v >= 85 ? '#52c41a' : v >= 70 ? '#faad14' : '#ff4d4f';
        return <Text strong style={{ color }}>⭐ {v}</Text>;
      },
    },
    {
      title: '操作', key: 'action', width: 180, fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button type="link" size="small" icon={<EditOutlined />}
              onClick={() => handleOpen(record)} />
          </Tooltip>
          <Tooltip title={record.status === 'active' ? '停用' : '启用'}>
            <Button type="link" size="small"
              icon={record.status === 'active' ? <StopOutlined /> : <CheckCircleOutlined />}
              onClick={() => handleToggleStatus(record.id)} />
          </Tooltip>
          <Popconfirm title={`确认删除「${record.name}」？`}
            onConfirm={() => handleDelete(record.id, record.name)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>👤 面试官库</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpen()}>
            添加面试官
          </Button>
        </Col>
      </Row>

      {/* 筛选栏 */}
      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: '12px 16px' }}>
        <Space wrap>
          <Input
            placeholder="搜索姓名 / 部门 / 职位..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            style={{ width: 260 }}
            allowClear
          />
          <Select
            placeholder="全部状态"
            value={statusFilter}
            onChange={setStatusFilter}
            allowClear
            style={{ width: 120 }}
            options={[
              { value: 'active', label: '在职' },
              { value: 'inactive', label: '停用' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
        </Space>
      </Card>

      {/* 表格 */}
      <Card>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ x: 1100 }}
          locale={{
            emptyText: (
              <EmptyGuide
                title="还没有面试官"
                description="添加面试官后即可在安排面试时选择"
                steps={[
                  { icon: stepIcons.interview, label: '填写面试官信息' },
                  { icon: stepIcons.approve, label: '设为活跃状态' },
                  { icon: stepIcons.schedule, label: '安排面试时选择' },
                ]}
              />
            ),
          }}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: t => `共 ${t} 位面试官` }}
        />
      </Card>

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editing ? '✏️ 编辑面试官' : '➕ 添加面试官'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        okText="保存"
        cancelText="取消"
        width={600}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ status: 'active' }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
                <Input placeholder="请输入面试官姓名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="position" label="职位">
                <Input placeholder="如：高级后端工程师" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="email" label="邮箱">
                <Input placeholder="email@example.com" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="phone" label="手机号">
                <Input placeholder="138xxxxx" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="department" label="所属部门">
            <Input placeholder="如：技术研发部" />
          </Form.Item>
          <Form.Item name="skills" label="擅长领域/技术栈">
            <Input placeholder="用逗号分隔，如：Python, 后端架构, 系统设计" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <TextArea rows={3} placeholder="其他补充信息..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default InterviewerManage;
