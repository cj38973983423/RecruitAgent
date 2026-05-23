import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Typography, Tag, Button, Space, Row, Col,
  Statistic, Empty, Alert, Modal, message, Steps,
  Spin,
} from 'antd';
import {
  ApartmentOutlined, CheckCircleOutlined, SyncOutlined,
  PlusOutlined, DeleteOutlined,
  RobotOutlined, AuditOutlined,
  RightCircleOutlined,
} from '@ant-design/icons';
import { listActiveWorkflows, deleteWorkflow } from '../api';

const { Title, Text, Paragraph } = Typography;

const JD_STEPS = [
  { key: 'requirement_collect', title: 'AI增强需求', desc: '自动补充完善' },
  { key: 'jd_generation', title: 'AI生成JD', desc: 'RAG增强' },
  { key: 'pending_review', title: '人工审查', desc: 'HR审核确认' },
  { key: 'done', title: '完成', desc: 'JD生效' },
];

function getJDStep(status: string, jdStatus: string | null): number {
  if (jdStatus === 'pending_review') return 2;
  if (status === 'completed') return 3;
  if (status === 'running' || status === 'in_progress') return 1;
  return 0;
}

const WorkflowList: React.FC = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const data = await listActiveWorkflows();
      setWorkflows(data || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  const handleDelete = (requestId: number, position: string) => {
    Modal.confirm({
      title: `确认删除「${position}」？`,
      content: '删除后将同时移除关联的 JD、工作流状态和日志，不可恢复。',
      okText: '确认删除', okType: 'danger', cancelText: '取消',
      onOk: async () => {
        try {
          await deleteWorkflow(requestId);
          message.success(`已删除「${position}」`);
          loadData();
        } catch (err: any) {
          message.error('删除失败: ' + (err?.response?.data?.detail || err.message));
        }
      },
    });
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 10000);
    return () => clearInterval(timer);
  }, []);

  const stats = {
    total: workflows.length,
    pending_review: workflows.filter(w => w.has_pending_review).length,
    active: workflows.filter(w => w.status === 'in_progress' || w.status === 'draft').length,
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <Title level={3}>
        <ApartmentOutlined style={{ marginRight: 8, color: '#3b82f6' }} />
        岗位生成流程
      </Title>
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        实时监控所有招聘流程的完整状态。AI 会自动增强模糊需求并生成 JD。
      </Paragraph>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="全部流程" value={stats.total} prefix={<ApartmentOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="待审查JD" value={stats.pending_review}
              valueStyle={{ color: '#3b82f6' }} prefix={<AuditOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic title="进行中" value={stats.active}
              valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/new')}>新建岗位</Button>
          <Button icon={<SyncOutlined />} onClick={loadData}>刷新</Button>
        </Space>
      </Card>

      {workflows.length === 0 ? (
        <Card>
          <Empty description={
            <Space direction="vertical" style={{ alignItems: 'center' }}>
              <span>还没有招聘流程</span>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/new')}>
                创建第一个招聘需求
              </Button>
            </Space>
          } />
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {workflows.map((w) => {
            const jdStep = getJDStep(w?.jd_workflow?.status, w?.jd_workflow?.jd_status);

            return (
              <Card
                key={w.request_id}
                hoverable
                style={{
                  borderLeft: `4px solid ${
                    w.has_pending_review ? '#3b82f6'
                    : w.status === 'completed' ? '#22c55e'
                    : '#d9d9d9'
                  }`,
                }}
                actions={[
                  <Button type="link" icon={<RightCircleOutlined />} key="detail"
                    onClick={() => navigate(`/workflow/${w.request_id}`)}>
                    查看详情
                  </Button>,
                  w.has_pending_review ? (
                    <Button type="link" key="review"
                      icon={<AuditOutlined style={{ color: '#3b82f6' }} />}
                      onClick={() => navigate('/review-jds')}>
                      前往审查
                    </Button>
                  ) : null,
                  <Button type="link" key="delete" danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => { e.stopPropagation(); handleDelete(w.request_id, w.position); }}>
                    删除
                  </Button>,
                ].filter(Boolean)}
              >
                <Row gutter={16} style={{ marginBottom: 8 }}>
                  <Col flex="auto">
                    <Space>
                      <span style={{ fontSize: 16, fontWeight: 600 }}>{w.position}</span>
                      <Text type="secondary">{w.department}</Text>
                      {w.has_pending_review && <Tag color="blue" icon={<AuditOutlined />}>待审查</Tag>}
                    </Space>
                  </Col>
                  <Col>
                    <Text type="secondary" style={{ fontSize: 12 }}>ID: {w.request_id}</Text>
                  </Col>
                </Row>

                <Row gutter={24}>
                  <Col span={24}>
                    <div style={{ marginBottom: 4 }}>
                      <RobotOutlined style={{ color: '#3b82f6', marginRight: 6 }} />
                      <Text strong style={{ fontSize: 13 }}>岗位生成</Text>
                    </div>
                    <Steps size="small" current={jdStep} style={{ marginTop: 6 }}
                      items={JD_STEPS.map((step, i) => ({
                        title: step.title,
                        description: step.desc,
                        status: i < jdStep ? 'finish' : i === jdStep ? 'process' : 'wait',
                      }))}
                    />
                  </Col>
                </Row>

                {w.has_pending_review && (
                  <Alert
                    type="success" showIcon style={{ marginTop: 12, fontSize: 13 }}
                    message={<span>JD 已生成，等待人工审查</span>}
                    action={
                      <Button size="small" type="primary" onClick={() => navigate('/review-jds')}>去审查</Button>
                    }
                  />
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default WorkflowList;
