import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Typography, Table, Tag, Space, Button, Modal,
  Input, message, Row, Col, Statistic, Descriptions, Divider,
  Empty, Tooltip, Progress, Select, Popconfirm,
} from 'antd';
import dayjs from 'dayjs';
import {
  UserOutlined, TeamOutlined, TrophyOutlined, CheckCircleOutlined,
  ScheduleOutlined, FileTextOutlined, StarOutlined,
  DollarOutlined, ThunderboltOutlined, RocketOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import {
  listCandidates, getCandidateStats, getCandidateDetail,
  deleteCandidate,
} from '../api';
import type {
  CandidateDetail, CandidateStats, CandidateListResponse,
  InterviewSummary, EvalSummary,
} from '../types';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  ai_pass: { label: 'AI通过', color: 'blue' },
  manual_pass: { label: '人工通过', color: 'green' },
};

const OFFER_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  draft: { label: 'Offer草稿', color: 'default' },
  sent: { label: 'Offer已发', color: 'blue' },
  accepted: { label: 'Offer已接受', color: 'green' },
  onboarded: { label: '已入职', color: 'purple' },
  rejected: { label: '已拒绝', color: 'red' },
  withdrawn: { label: '已撤回', color: 'orange' },
};

const RECOMMEND_CONFIG: Record<string, { label: string; color: string }> = {
  pass: { label: '✅ 通过', color: 'green' },
  hold: { label: '⏳ 待定', color: 'orange' },
  reject: { label: '❌ 淘汰', color: 'red' },
};

const ROUND_COLORS: Record<string, string> = {
  first: '#3b82f6', second: '#8b5cf6', third: '#f59e0b', hr: '#10b981',
};

const CandidatesManage: React.FC = () => {
  const [candidates, setCandidates] = useState<CandidateDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<CandidateStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  const [detailModal, setDetailModal] = useState<CandidateDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: 50 };
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const [data, s] = await Promise.all([
        listCandidates(params),
        getCandidateStats(),
      ]);
      setCandidates(data.items ?? []);
      setTotal(data.total);
      setStats(s);
    } catch {
      message.error('加载候选人列表失败');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleViewDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const detail = await getCandidateDetail(id);
      setDetailModal(detail);
    } catch {
      message.error('加载候选人详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  // ── 评价渲染 ──
  const renderEval = (e: EvalSummary, idx: number) => {
    const roundColor = ROUND_COLORS[e.round] || '#999';
    return (
      <div key={idx} style={{
        background: '#fafafa', borderRadius: 6, padding: '10px 14px',
        borderLeft: `3px solid ${roundColor}`, marginBottom: 8,
      }}>
        <Space style={{ marginBottom: 4 }}>
          <Tag color={roundColor} style={{ fontWeight: 600 }}>{e.round_label}</Tag>
          {e.recommendation && (
            <Tag color={RECOMMEND_CONFIG[e.recommendation]?.color || 'default'}>
              {RECOMMEND_CONFIG[e.recommendation]?.label || e.recommendation}
            </Tag>
          )}
          <Text type="secondary" style={{ fontSize: 12 }}>{e.evaluator && `评价人: ${e.evaluator}`}</Text>
          {e.created_at && <Text type="secondary" style={{ fontSize: 11 }}>{dayjs(e.created_at).format('MM-DD HH:mm')}</Text>}
        </Space>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 4 }}>
          {e.tech_score != null && (
            <Tooltip title="技术能力">
              <span><Text type="secondary" style={{ fontSize: 12 }}>技术:</Text>
                <Text style={{ fontSize: 13, fontWeight: 600, color: e.tech_score >= 70 ? '#52c41a' : '#faad14', marginLeft: 4 }}>{e.tech_score}</Text>
              </span>
            </Tooltip>
          )}
          {e.communication_score != null && (
            <Tooltip title="沟通能力">
              <span><Text type="secondary" style={{ fontSize: 12 }}>沟通:</Text>
                <Text style={{ fontSize: 13, fontWeight: 600, color: e.communication_score >= 70 ? '#52c41a' : '#faad14', marginLeft: 4 }}>{e.communication_score}</Text>
              </span>
            </Tooltip>
          )}
          {e.overall_score != null && (
            <Tooltip title="综合评分">
              <span><Text type="secondary" style={{ fontSize: 12 }}>综合:</Text>
                <Text style={{ fontSize: 13, fontWeight: 700, color: '#722ed1', marginLeft: 4 }}>{e.overall_score}</Text>
              </span>
            </Tooltip>
          )}
        </div>
        {e.strengths && <Text style={{ fontSize: 12, display: 'block', marginTop: 2 }}>💪 {e.strengths}</Text>}
        {e.weaknesses && <Text style={{ fontSize: 12, display: 'block' }}>⚠️ {e.weaknesses}</Text>}
        {e.conclusion && <Text style={{ fontSize: 12, display: 'block' }}>📝 {e.conclusion}</Text>}
      </div>
    );
  };

  // ── 面试轮次渲染 ──
  const renderInterview = (iv: InterviewSummary) => (
    <div key={iv.id} style={{ marginBottom: 12 }}>
      <Space style={{ marginBottom: 4 }}>
        <Tag color={ROUND_COLORS[iv.round] || '#999'}>{iv.round_label}</Tag>
        <Tag>{iv.status === 'completed' ? '已完成' : iv.status}</Tag>
        {iv.interviewer_name && <Text type="secondary" style={{ fontSize: 12 }}>面试官: {iv.interviewer_name}</Text>}
        {iv.scheduled_at && <Text type="secondary" style={{ fontSize: 12 }}>{dayjs(iv.scheduled_at).format('MM-DD HH:mm')}</Text>}
      </Space>
      {iv.evaluations.length > 0 ? (
        iv.evaluations.map(renderEval)
      ) : (
        <Text type="secondary" style={{ fontSize: 12, marginLeft: 24 }}>暂无评价记录</Text>
      )}
    </div>
  );

  // ── 表格列 ──
  const columns = [
    {
      title: '姓名', dataIndex: 'name', key: 'name', width: 100,
      render: (v: string, r: CandidateDetail) => (
        <Space><UserOutlined /><Text strong>{v || '未知'}</Text></Space>
      ),
    },
    {
      title: '部门 / 岗位', key: 'dept_jd', width: 180, ellipsis: true,
      render: (_: unknown, r: CandidateDetail) => (
        <Space size={4} wrap>
          {r.department && <Tag color="blue" style={{ margin: 0 }}>{r.department}</Tag>}
          {r.jd_title && <Text style={{ fontSize: 12, color: '#666' }}>{r.jd_title}</Text>}
          {!r.department && !r.jd_title && <Text type="secondary">-</Text>}
        </Space>
      ),
    },
    {
      title: '技能', dataIndex: 'skills', key: 'skills', width: 200, ellipsis: true,
      render: (v: string | string[]) => {
        if (!v) return '-';
        const skills = Array.isArray(v) ? v : v.split(',').filter(Boolean);
        return skills.slice(0, 4).map(s => (
          <Tag key={s} style={{ margin: '1px 2px', fontSize: 11 }}>{s.trim()}</Tag>
        ));
      },
    },
    { title: '经验', dataIndex: 'experience_years', key: 'exp', width: 60,
      render: (v: number) => v != null ? `${v}年` : '-' },
    {
      title: 'AI评分', dataIndex: 'ai_score', key: 'ai_score', width: 80,
      render: (v: number, r: CandidateDetail) => (
        v != null
          ? <Tag color={v >= 80 ? 'green' : v >= 60 ? 'blue' : 'red'}>{v}</Tag>
          : <Text type="secondary">-</Text>
      ),
    },
    {
      title: '面试轮次', dataIndex: 'interviews_total', key: 'rounds', width: 80,
      render: (v: number) => <Tag>{v}轮</Tag>,
    },
    {
      title: '最佳轮次', dataIndex: 'best_round', key: 'best', width: 80,
      render: (v: string) => v ? <Tag color="purple">{v}</Tag> : '-',
    },
    {
      title: '均分', dataIndex: 'avg_score', key: 'avg', width: 70,
      render: (v: number) => v != null
        ? <Text style={{ fontWeight: 600, color: v >= 80 ? '#52c41a' : v >= 60 ? '#faad14' : '#ff4d4f' }}>{v}</Text>
        : '-',
    },
    {
      title: 'Offer', dataIndex: 'offer_status', key: 'offer', width: 100,
      render: (v: string) => {
        if (!v) return <Tag>待定</Tag>;
        const cfg = OFFER_STATUS_CONFIG[v];
        return <Tag color={cfg?.color}>{cfg?.label || v}</Tag>;
      },
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => {
        const cfg = STATUS_CONFIG[v];
        return <Tag color={cfg?.color}>{cfg?.label || v}</Tag>;
      },
    },
    {
      title: '操作', key: 'action', width: 130,
      render: (_: unknown, r: CandidateDetail) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<FileTextOutlined />}
            onClick={() => handleViewDetail(r.id)}>
            详情
          </Button>
          <Popconfirm title="确定从候选人库移除此人？"
            description="简历数据会保留，可从简历管理中重新筛选"
            onConfirm={async () => {
              try {
                await deleteCandidate(r.id);
                message.success('已从候选人库移除');
                fetchData();
              } catch (err: any) {
                message.error('删除失败: ' + (err?.response?.data?.detail || err.message));
              }
            }}>
            <Button danger size="small" type="link" icon={<DeleteOutlined />}>移除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* ── 统计卡片 ── */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="候选人库" value={stats?.total_in_pool ?? '-'}
            prefix={<TeamOutlined />} valueStyle={{ color: '#3b82f6' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已面试" value={stats?.total_interviewed ?? '-'}
            prefix={<ScheduleOutlined />} valueStyle={{ color: '#8b5cf6' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已发Offer" value={stats?.offered_count ?? '-'}
            prefix={<DollarOutlined />} valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已入职" value={stats?.onboarded_count ?? '-'}
            prefix={<RocketOutlined />} valueStyle={{ color: '#722ed1' }} /></Card>
        </Col>
      </Row>

      {/* ── 主卡片 ── */}
      <Card
        title={<Space><TeamOutlined style={{ fontSize: 18 }} /> 候选人库</Space>}
        extra={
          <Space>
            <Select placeholder="筛选" allowClear style={{ width: 120 }}
              value={statusFilter || undefined}
              onChange={v => setStatusFilter(v || '')}
              options={[
                { value: '', label: '全部' },
                { value: 'no_offer', label: '待Offer' },
                { value: 'has_offer', label: '已有Offer' },
              ]}
            />
            <Search placeholder="搜索姓名..." allowClear
              value={search} onChange={e => setSearch(e.target.value)}
              onSearch={() => fetchData()} style={{ width: 200 }} />
          </Space>
        }
      >
        {candidates.length === 0 ? (
          <Empty description={
            <Space direction="vertical" style={{ textAlign: 'center' }}>
              <Text type="secondary">暂无候选人</Text>
              <Text type="secondary">候选人通过简历筛选和面试后会自动出现在这里</Text>
            </Space>
          } />
        ) : (
          <Table dataSource={candidates} columns={columns}
            rowKey="id" size="small" loading={loading}
            pagination={{ total, pageSize: 50, showTotal: t => `共 ${t} 人`, size: 'small' }}
            scroll={{ x: 1000 }}
          />
        )}
      </Card>

      {/* ── 候选人详情弹窗 ── */}
      <Modal title={
        <Space>
          <UserOutlined style={{ color: '#3b82f6' }} />
          <span>{detailModal?.name || '候选人详情'}</span>
          {detailModal?.jd_title && <Tag>{detailModal.jd_title}</Tag>}
        </Space>
      }
        open={!!detailModal}
        onCancel={() => setDetailModal(null)}
        footer={null}
        width={800}
        loading={detailLoading}
      >
        {detailModal && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {/* 基本信息 */}
            <Card size="small" title="📋 基本信息" styles={{ header: { fontSize: 14 } }}>
              <Descriptions column={2} size="small">
                <Descriptions.Item label="姓名">{detailModal.name || '-'}</Descriptions.Item>
                <Descriptions.Item label="经验年限">{detailModal.experience_years != null ? `${detailModal.experience_years}年` : '-'}</Descriptions.Item>
                <Descriptions.Item label="AI评分">
                  {detailModal.ai_score != null
                    ? <Tag color={detailModal.ai_score >= 80 ? 'green' : detailModal.ai_score >= 60 ? 'blue' : 'red'}>{detailModal.ai_score}</Tag>
                    : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="AI推荐">{detailModal.ai_recommended ? '✅ 推荐' : '-'}</Descriptions.Item>
                <Descriptions.Item label="技能" span={2}>
                  {detailModal.skills
                    ? (Array.isArray(detailModal.skills)
                        ? detailModal.skills.map(s => <Tag key={s}>{s}</Tag>)
                        : detailModal.skills.split(',').map(s => <Tag key={s}>{s.trim()}</Tag>))
                    : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="AI理由" span={2}>{detailModal.ai_reason || '-'}</Descriptions.Item>
                <Descriptions.Item label="备注" span={2}>{detailModal.notes || '-'}</Descriptions.Item>
              </Descriptions>
            </Card>

            {/* 深度分析 */}
            {detailModal.deep_analysis && (
              <Card size="small" title="🔍 深度分析" styles={{ header: { fontSize: 14 } }}>
                <Space direction="vertical" style={{ width: '100%' }} size="small">
                  {detailModal.deep_analysis.project_authenticity && (
                    <div>
                      <Text strong>项目真实性: </Text>
                      <Text>{(detailModal.deep_analysis.project_authenticity as any).score ?? '-'}/100</Text>
                      {(detailModal.deep_analysis.project_authenticity as any).details &&
                        <Paragraph style={{ fontSize: 12, margin: '4px 0' }}>
                          {(detailModal.deep_analysis.project_authenticity as any).details}
                        </Paragraph>}
                    </div>
                  )}
                  {detailModal.deep_analysis.risk_warnings && Array.isArray(detailModal.deep_analysis.risk_warnings) && (
                    <div>
                      <Text strong>风险预警: </Text>
                      {(detailModal.deep_analysis.risk_warnings as any[]).map((w, i) => (
                        <Tag key={i} color={w.severity === 'high' ? 'red' : w.severity === 'medium' ? 'orange' : 'blue'}>
                          {w.type}
                        </Tag>
                      ))}
                    </div>
                  )}
                </Space>
              </Card>
            )}

            {/* 面试评价 */}
            <Card size="small" title={
              <Space><ScheduleOutlined /> 面试评价 <Tag>{detailModal.interviews_total}轮</Tag></Space>
            } styles={{ header: { fontSize: 14 } }}>
              {detailModal.interviews.length > 0 ? (
                detailModal.interviews.map(renderInterview)
              ) : (
                <Text type="secondary">暂无面试记录</Text>
              )}
            </Card>

            {/* Offer 信息 */}
            {detailModal.offer && (
              <Card size="small" title={<Space><DollarOutlined /> Offer 信息</Space>}
                styles={{ header: { fontSize: 14 } }}>
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="薪资">{detailModal.offer.salary || '-'}</Descriptions.Item>
                  <Descriptions.Item label="股权">{detailModal.offer.equity || '-'}</Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={OFFER_STATUS_CONFIG[detailModal.offer.status]?.color}>
                      {OFFER_STATUS_CONFIG[detailModal.offer.status]?.label || detailModal.offer.status}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="入职日期">
                    {detailModal.offer.start_date ? dayjs(detailModal.offer.start_date).format('YYYY-MM-DD') : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="发送时间">
                    {detailModal.offer.sent_at ? dayjs(detailModal.offer.sent_at).format('MM-DD HH:mm') : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="接受时间">
                    {detailModal.offer.accepted_at ? dayjs(detailModal.offer.accepted_at).format('MM-DD HH:mm') : '-'}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            )}

            {/* 教育 & 工作经历 */}
            <Row gutter={12}>
              {detailModal.education && (
                <Col span={12}>
                  <Card size="small" title="🎓 教育经历" styles={{ header: { fontSize: 14 } }}>
                    <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{detailModal.education}</Text>
                  </Card>
                </Col>
              )}
              {detailModal.work_experience && (
                <Col span={12}>
                  <Card size="small" title="💼 工作经历" styles={{ header: { fontSize: 14 } }}>
                    <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{detailModal.work_experience}</Text>
                  </Card>
                </Col>
              )}
            </Row>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default CandidatesManage;
