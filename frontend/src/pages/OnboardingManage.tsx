import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Typography, Table, Tag, Space, Button, Modal,
  Input, message, Tabs, Row, Col, Statistic, DatePicker, Empty,
  Popconfirm,
} from 'antd';
import dayjs from 'dayjs';
import {
  CheckCircleOutlined, ClockCircleOutlined, UserOutlined,
  TeamOutlined, DollarOutlined, CalendarOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import {
  listPendingOnboarding, listCompletedOnboarding, completeOnboarding,
  deleteOnboarding,
} from '../api';
import type { OnboardingItem } from '../types';

const { Title, Text } = Typography;
const { TextArea } = Input;

const OnboardingManage: React.FC = () => {
  const [pending, setPending] = useState<OnboardingItem[]>([]);
  const [completed, setCompleted] = useState<OnboardingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [tabKey, setTabKey] = useState('pending');

  // 确认入职弹窗
  const [completeModal, setCompleteModal] = useState<OnboardingItem | null>(null);
  const [actualDate, setActualDate] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [completing, setCompleting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [p, c] = await Promise.all([
        listPendingOnboarding(),
        listCompletedOnboarding(),
      ]);
      setPending(Array.isArray(p) ? p : []);
      setCompleted(Array.isArray(c) ? c : []);
    } catch {
      message.error('加载入职列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleComplete = async () => {
    if (!completeModal) return;
    setCompleting(true);
    try {
      await completeOnboarding(completeModal.id, {
        actual_start_date: actualDate || undefined,
        notes: notes || undefined,
      });
      message.success(`🎊 ${completeModal.candidate_name} 已确认入职！`);
      setCompleteModal(null);
      setActualDate('');
      setNotes('');
      fetchData();
    } catch (err: any) {
      message.error('操作失败: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setCompleting(false);
    }
  };

  // ── 待入职表格 ──
  const pendingColumns = [
    {
      title: '候选人', dataIndex: 'candidate_name', key: 'name',
      render: (v: string) => (
        <Space><UserOutlined /><Text strong>{v}</Text></Space>
      ),
    },
    { title: '职位', dataIndex: 'position_name', key: 'pos', ellipsis: true },
    { title: '部门', dataIndex: 'department', key: 'dept' },
    { title: '薪资', dataIndex: 'salary', key: 'salary', render: (v: string) => <><DollarOutlined /> {v}</> },
    {
      title: '预期入职', dataIndex: 'start_date', key: 'start_date',
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : <Text type="secondary">待确认</Text>,
    },
    {
      title: '接受时间', dataIndex: 'accepted_at', key: 'accepted_at',
      render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '操作', key: 'action', width: 180,
      render: (_: unknown, record: OnboardingItem) => (
        <Space size={4}>
          <Button type="primary" icon={<CheckCircleOutlined />} size="small"
            onClick={() => {
              setCompleteModal(record);
              setActualDate(record.start_date || '');
              setNotes('');
            }}>
            确认入职
          </Button>
          <Popconfirm title="确定撤销此入职记录？"
            description="该记录将回退到 Offer 管理"
            onConfirm={async () => {
              try {
                await deleteOnboarding(record.id);
                message.success('已撤销入职记录');
                fetchData();
              } catch (err: any) {
                message.error('操作失败: ' + (err?.response?.data?.detail || err.message));
              }
            }}>
            <Button danger size="small" icon={<DeleteOutlined />}>撤销</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ── 已入职表格 ──
  const completedColumns = [
    {
      title: '候选人', dataIndex: 'candidate_name', key: 'name',
      render: (v: string) => (
        <Space><UserOutlined /><Text strong>{v}</Text></Space>
      ),
    },
    { title: '职位', dataIndex: 'position_name', key: 'pos', ellipsis: true },
    { title: '部门', dataIndex: 'department', key: 'dept' },
    {
      title: '入职日期', dataIndex: 'start_date', key: 'start_date',
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD') : '-',
    },
    {
      title: '入职完成', dataIndex: 'onboarded_at', key: 'onboarded_at',
      render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '备注', dataIndex: 'notes', key: 'notes', width: 200,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '操作', key: 'action', width: 100,
      render: (_: unknown, record: OnboardingItem) => (
        <Popconfirm title="确定撤销此入职记录？"
          description="将回退到 Offer 已接受状态"
          onConfirm={async () => {
            try {
              await deleteOnboarding(record.id);
              message.success('已撤销入职记录');
              fetchData();
            } catch (err: any) {
              message.error('操作失败: ' + (err?.response?.data?.detail || err.message));
            }
          }}>
          <Button danger size="small" icon={<DeleteOutlined />}>撤销</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="待入职" value={pending.length}
            prefix={<ClockCircleOutlined />} valueStyle={{ color: '#faad14' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已入职" value={completed.length}
            prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="入职转化率"
            value={pending.length + completed.length > 0
              ? Math.round(completed.length / (pending.length + completed.length) * 100)
              : 0}
            suffix="%" valueStyle={{ color: '#722ed1' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="总入职人数" value={completed.length}
            prefix={<TeamOutlined />} valueStyle={{ color: '#3b82f6' }} /></Card>
        </Col>
      </Row>

      <Card title={<Space><TeamOutlined /> 入职管理</Space>}>
        <Tabs activeKey={tabKey} onChange={setTabKey}
          items={[
            { key: 'pending', label: <span><ClockCircleOutlined /> 待入职 ({pending.length})</span> },
            { key: 'completed', label: <span><CheckCircleOutlined /> 已入职 ({completed.length})</span> },
          ]}
        />

        {tabKey === 'pending' && (
          pending.length === 0 ? (
            <Empty description={<Text type="secondary">暂无待入职候选人 — 接受 Offer 后会出现在这里</Text>} />
          ) : (
            <Table dataSource={pending} columns={pendingColumns}
              rowKey="id" size="small" loading={loading} />
          )
        )}

        {tabKey === 'completed' && (
          completed.length === 0 ? (
            <Empty description={<Text type="secondary">暂无已入职记录</Text>} />
          ) : (
            <Table dataSource={completed} columns={completedColumns}
              rowKey="id" size="small" loading={loading} />
          )
        )}
      </Card>

      {/* ── 确认入职弹窗 ── */}
      <Modal title={<Space><CheckCircleOutlined style={{ color: '#52c41a' }} /> 确认入职</Space>}
        open={!!completeModal}
        onOk={handleComplete}
        onCancel={() => { setCompleteModal(null); setActualDate(''); setNotes(''); }}
        confirmLoading={completing}
        okText="确认入职"
        cancelText="取消"
        width={500}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Card size="small" style={{ background: '#f0fdf4', border: '1px solid #bbf7d0' }}>
            <Space>
              <UserOutlined style={{ color: '#22c55e', fontSize: 20 }} />
              <div>
                <Text strong style={{ fontSize: 15 }}>{completeModal?.candidate_name}</Text>
                <br />
                <Text type="secondary">{completeModal?.position_name} · {completeModal?.department}</Text>
              </div>
            </Space>
          </Card>

          <div>
            <Text type="secondary">实际入职日期</Text>
            <DatePicker style={{ width: '100%' }}
              value={actualDate ? dayjs(actualDate) : null}
              onChange={d => setActualDate(d?.toISOString() || '')} />
          </div>

          <div>
            <Text type="secondary">备注</Text>
            <TextArea rows={3} value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="入职备注（工位安排、设备申请等）" />
          </div>

          <Text type="secondary" style={{ fontSize: 12 }}>
            💡 确认入职后，该候选人将从未入职列表移至已入职列表，招聘流程完成。
          </Text>
        </Space>
      </Modal>
    </div>
  );
};

export default OnboardingManage;
