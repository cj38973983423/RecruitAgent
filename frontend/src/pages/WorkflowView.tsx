import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Typography, Tag, Button, Spin, Space, message,
  Steps, Alert, Table, Empty, Row, Col, Statistic, Timeline,
} from 'antd';
import {
  getWorkflowState,
} from '../api';
import {
  RobotOutlined, UserOutlined, FormOutlined, AuditOutlined,
  CheckCircleOutlined, SyncOutlined,
  ArrowLeftOutlined, ClockCircleOutlined, FileTextOutlined,
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

const JD_STEPS = [
  { title: 'AI增强需求', desc: '自动补充完善' },
  { title: 'AI生成JD', desc: 'RAG知识增强' },
  { title: '人工审查', desc: 'HR审核确认' },
  { title: '完成', desc: 'JD生效' },
];

const SC_STEPS = [
  { title: '简历收集' },
  { title: 'AI评分' },
  { title: '候选池' },
  { title: '面试安排' },
  { title: '面试题' },
  { title: '执行面试' },
  { title: '面试评价' },
  { title: 'Offer管理' },
  { title: 'Offer/入职' },
];

const SC_NODE_ORDER = ['resume_collect', 'resume_auto_screen', 'candidate_pool', 'interview_schedule', 'interview_questions', 'interview_execute', 'interview_evaluate', 'offer_manage', 'onboarding'];

const WorkflowView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const timerRef = useRef<number | null>(null);

  const loadState = async (showRefresh = false) => {
    if (!id) return;
    if (showRefresh) setRefreshing(true);
    try {
      const data = await getWorkflowState(Number(id));
      setState(data);
    } catch (err: any) {
      if (!state) {
        message.error('加载失败: ' + (err?.response?.data?.detail || err.message));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadState();
    timerRef.current = window.setInterval(() => loadState(), 5000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [id]);

  const jd = state?.jd_workflow;
  const sc = state?.screening_workflow;
  const hasJD = jd && jd.current_node;
  const hasSC = sc && sc.current_node;

  let jdStepIdx = 0;
  if (jd) {
    if (jd.jd_status === 'pending_review') jdStepIdx = 2;
    else if (jd.status === 'completed') jdStepIdx = 3;
    else if (jd.status === 'running' || jd.status === 'in_progress') jdStepIdx = jd.jd_id ? 2 : 1;
  }

  const scIdx = hasSC ? SC_NODE_ORDER.indexOf(sc?.current_node) : -1;

  if (loading && !state) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: '12px 24px' }}>
        <Row gutter={16} align="middle">
          <Col>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/workflows')} />
          </Col>
          <Col flex="auto">
            <Space>
              <Title level={4} style={{ margin: 0 }}>{state?.position || '未知岗位'}</Title>
              <Text type="secondary">{state?.department}</Text>
              {jd?.jd_status === 'pending_review' && <Tag color="blue" icon={<AuditOutlined />}>待审查</Tag>}
              {jd?.status === 'completed' && !jd?.jd_status && <Tag color="green">JD已完成</Tag>}
            </Space>
          </Col>
          <Col>
            <Space>
              <Button icon={<SyncOutlined spin={refreshing} />} onClick={() => loadState(true)} size="small">刷新</Button>
              <Button size="small" onClick={() => navigate('/workflows')}>返回列表</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={hasSC ? 12 : 18}>
          <Card
            title={
              <Space>
                <RobotOutlined style={{ color: '#3b82f6' }} />
                <span>岗位生成工作流</span>
                {jd?.current_node && (
                  <Tag color={jd.status === 'completed' ? 'green' : 'blue'}>
                    {jd.jd_status === 'pending_review' ? '待审查' : jd.current_node}
                  </Tag>
                )}
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            {!hasJD ? (
              <Empty description="JD 工作流未启动" />
            ) : (
              <>
                <Steps current={jdStepIdx} size="small" style={{ marginBottom: 20 }}
                  items={JD_STEPS.map((s, i) => ({
                    title: s.title, description: s.desc,
                    status: i < jdStepIdx ? 'finish' : i === jdStepIdx ? 'process' : 'wait',
                  }))}
                />

                {state?.raw_requirements && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ fontSize: 13 }}>📝 原始需求：</Text>
                    <Paragraph ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                      style={{ margin: '4px 0 0', fontSize: 13, background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                      {state.raw_requirements}
                    </Paragraph>
                  </div>
                )}

                {jd.enhanced_jd_text && (
                  <Card size="small"
                    title={<Space><FileTextOutlined /> AI 生成的 JD</Space>}
                    style={{ marginTop: 12, background: '#fafafa' }}
                    extra={jd.jd_status === 'pending_review' && (
                      <Button size="small" type="primary" onClick={() => navigate('/review-jds')}>
                        前往审查
                      </Button>
                    )}
                  >
                    <div style={{
                      maxHeight: 300, overflow: 'auto',
                      whiteSpace: 'pre-wrap', fontSize: 13,
                      fontFamily: 'monospace', lineHeight: 1.6,
                    }}>
                      {jd.enhanced_jd_text}
                    </div>
                  </Card>
                )}

                {jd.jd_status === 'pending_review' && (
                  <Alert
                    message="📋 JD 已生成，请前往「岗位人工审查」页面审核"
                    type="warning" showIcon style={{ marginTop: 12 }}
                    action={<Button size="small" type="primary" onClick={() => navigate('/review-jds')}>前往审查</Button>}
                  />
                )}
                {jd.status === 'completed' && !jd.jd_status && (
                  <Alert message="✅ JD 生成完成" type="success" showIcon style={{ marginTop: 12 }} />
                )}
                {jd.error && (
                  <Alert message={jd.error} type="error" showIcon closable style={{ marginTop: 12 }} />
                )}
              </>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={hasSC ? 12 : 0}>
          {hasSC ? (
            <Card
              title={
                <Space>
                  <UserOutlined style={{ color: '#22c55e' }} />
                  <span>简历筛选工作流</span>
                  <Tag color={sc.status === 'completed' ? 'green' : 'blue'}>{sc.current_node}</Tag>
                </Space>
              }
              style={{ marginBottom: 16, height: '100%' }}
            >
              <Steps size="small" current={scIdx} style={{ marginBottom: 16 }}
                items={SC_STEPS.map((s, i) => ({
                  title: s.title,
                  status: i < scIdx ? 'finish' : i === scIdx ? 'process' : 'wait',
                }))}
              />
              <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
                <Col span={8}><Statistic title="候选池" value={sc?.candidate_pool?.length || 0} suffix="人" valueStyle={{ fontSize: 18 }} /></Col>
                <Col span={8}><Statistic title="已评分" value={sc?.stats?.ai_screened || 0} suffix="人" valueStyle={{ fontSize: 18 }} /></Col>
                <Col span={8}><Statistic title="已淘汰" value={sc?.stats?.ai_rejected || 0} suffix="人" valueStyle={{ fontSize: 18, color: '#ef4444' }} /></Col>
              </Row>
              {sc?.candidate_pool && sc.candidate_pool.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Text strong>⭐ 候选池（按分数排序）</Text>
                  <Table dataSource={sc.candidate_pool}
                    columns={[
                      { title: '姓名', dataIndex: 'name', width: 80 },
                      { title: '分数', dataIndex: 'score', width: 70,
                        render: (v: number) => <Tag color={v >= 80 ? 'green' : v >= 60 ? 'blue' : 'red'}>{v}</Tag> },
                      { title: '技能', dataIndex: 'skills', render: (s: string[]) => (s || []).slice(0, 3).join(', ') },
                      { title: '经验', dataIndex: 'experience_years', width: 60, render: (v: number) => `${v}年` },
                    ]}
                    rowKey="id" size="small" pagination={false}
                  />
                </div>
              )}
            </Card>
          ) : (
            <Card style={{ height: '100%' }}>
              <div style={{ textAlign: 'center', padding: 40 }}>
                <ClockCircleOutlined style={{ fontSize: 40, color: '#d9d9d9' }} />
                <Paragraph type="secondary" style={{ marginTop: 12 }}>
                  简历筛选工作流将在 JD 审查通过后自动启动
                </Paragraph>
                {jd?.jd_status === 'pending_review' && (
                  <Button type="primary" onClick={() => navigate('/review-jds')}>前往审查 JD</Button>
                )}
              </div>
            </Card>
          )}
        </Col>
      </Row>

      <Card title={<Space><ClockCircleOutlined /> 流程日志</Space>} size="small" style={{ marginTop: 16 }}>
        <Timeline
          items={[
            ...(state?.raw_requirements ? [{
              children: <span>创建招聘需求：<Text code>{state.position}</Text></span>,
              color: 'blue',
            }] : []),
            ...(jd?.jd_id ? [{
              children: <span>AI 增强生成 JD 完成（ID: {jd.jd_id}）</span>,
              color: 'green',
            }] : []),
            ...(jd?.jd_status === 'pending_review' ? [{
              children: <span>⏳ 等待 HR 人工审查</span>,
              color: 'orange',
            }] : []),
            ...(sc ? [{
              children: <span>筛选工作流已启动（{sc.current_node}）</span>,
              color: 'green',
            }] : []),
          ]}
        />
      </Card>
    </div>
  );
};

export default WorkflowView;
