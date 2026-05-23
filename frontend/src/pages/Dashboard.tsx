import React, { useEffect, useState } from 'react';
import {
  Card, Row, Col, Statistic, Table, Tag, Typography, Progress, Space, Divider,
} from 'antd';
import {
  TeamOutlined, FileSearchOutlined, ScheduleOutlined,
  UserOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ClockCircleOutlined, RocketOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import http, { getDashboardStats } from '../api';
import { EmptyGuide, stepIcons } from '../components/EmptyGuide';
import type { DashboardStats } from '../types';

const { Title, Text } = Typography;

const ROUND_LABELS: Record<string, string> = {
  first: '一面', second: '二面', third: '三面', hr: 'HR面',
};
const ROUND_COLORS: Record<string, string> = {
  first: '#3b82f6', second: '#8b5cf6', third: '#f59e0b', hr: '#10b981',
};

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardStats().then(data => {
      setStats(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Title level={4} type="secondary">加载数据中...</Title>
      </div>
    );
  }

  const isEmpty = !stats || (!stats.resumes?.total && !stats.requests?.total && !stats.interviews?.total);
  if (isEmpty) {
    return (
      <div>
        <Title level={3} style={{ marginBottom: 20 }}>📊 招聘数据总览</Title>
        <EmptyGuide
          title="还没有招聘数据"
          description="开始使用系统后，这里会展示核心指标和招聘漏斗"
          steps={[
            { icon: stepIcons.jd, label: '创建岗位需求' },
            { icon: stepIcons.upload, label: '上传简历' },
            { icon: stepIcons.schedule, label: '安排面试' },
          ]}
        />
      </div>
    );
  }

  const { requests, resumes, interviews, interviewers, pipeline } = stats;
  const totalPool = resumes.in_pool || 0;
  const totalProgress = pipeline.interviews_completed || 0;

  return (
    <div>
      <Title level={3} style={{ marginBottom: 20 }}>📊 招聘数据总览</Title>

      {/* ═══ 招聘流程指标 ═══ */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={12} md={8}>
          <Card hoverable size="small">
            <Statistic
              title="招聘需求"
              value={requests.total || 0}
              prefix={<RocketOutlined style={{ color: '#3b82f6' }} />}
              suffix={
                <span style={{ fontSize: 13 }}>
                  {requests.headcount_total != null && requests.hired_count != null
                    ? `已招 ${requests.hired_count}/${requests.headcount_total} 人`
                    : `${requests.active || 0} 进行中`}
                </span>
              }
              valueStyle={{ color: '#3b82f6' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={8}>
          <Card hoverable size="small">
            <Statistic
              title="简历候选池"
              value={totalPool}
              prefix={<TeamOutlined style={{ color: '#10b981' }} />}
              suffix={`/ ${resumes.total || 0} 总计`}
              valueStyle={{ color: '#10b981' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={8}>
          <Card hoverable size="small">
            <Statistic
              title="面试场次"
              value={interviews.total || 0}
              prefix={<ScheduleOutlined style={{ color: '#8b5cf6' }} />}
              suffix={`${interviews.completed || 0} 已完成`}
              valueStyle={{ color: '#8b5cf6' }}
            />
          </Card>
        </Col>
      </Row>

      {/* ═══ 录用环节指标 ═══ */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={12} md={6}>
          <Card hoverable size="small">
            <Statistic
              title="已发送 Offer"
              value={pipeline?.offers_sent || 0}
              prefix={<DollarOutlined style={{ color: '#f59e0b' }} />}
              valueStyle={{ color: '#f59e0b' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card hoverable size="small">
            <Statistic
              title="已接受 Offer"
              value={pipeline?.offers_accepted || 0}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card hoverable size="small">
            <Statistic
              title="已入职"
              value={pipeline?.onboarded || 0}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              suffix={`人`}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card hoverable size="small">
            <Statistic
              title="面试官库"
              value={interviewers.active || 0}
              prefix={<UserOutlined style={{ color: '#64748b' }} />}
              suffix={`/ ${interviewers.total || 0} 总计`}
              valueStyle={{ color: '#64748b' }}
            />
          </Card>
        </Col>
      </Row>

      {/* ═══ 简历状态 + 面试轮次 ═══ */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* 简历状态分布 */}
        <Col xs={24} md={12}>
          <Card title="📄 简历状态分布" size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <ResumeBar label="AI 通过" color="blue" count={resumes.ai_pass || 0} total={resumes.total || 1} icon="🤖" />
              <ResumeBar label="AI 淘汰" color="red" count={resumes.ai_reject || 0} total={resumes.total || 1} icon="🤖" />
              <ResumeBar label="人工通过" color="green" count={resumes.manual_pass || 0} total={resumes.total || 1} icon="👤" />
              <ResumeBar label="待处理" color="default" count={resumes.pending || 0} total={resumes.total || 1} icon="⏳" />
            </Space>
            <Divider style={{ margin: '8px 0' }} />
            <Text type="secondary" style={{ fontSize: 13 }}>
              候选池（AI通过 + 人工通过）：<Text strong style={{ color: '#10b981' }}>{totalPool} 人</Text>
            </Text>
          </Card>
        </Col>

        {/* 面试轮次分布 */}
        <Col xs={24} md={12}>
          <Card title="🎯 面试轮次分布" size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              {Object.entries(interviews.by_round || {}).map(([round, count]: any) => {
                const maxCount = Math.max(...Object.values(interviews.by_round || {}), 1);
                const pct = Math.round((count / maxCount) * 100);
                return (
                  <div key={round}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 13 }}>
                        <Tag color={ROUND_COLORS[round]} style={{ fontSize: 11 }}>{ROUND_LABELS[round] || round}</Tag>
                      </Text>
                      <Text strong style={{ fontSize: 13 }}>{count} 场</Text>
                    </div>
                    <Progress
                      percent={pct}
                      showInfo={false}
                      strokeColor={ROUND_COLORS[round]}
                      trailColor="#f0f0f0"
                      size="small"
                    />
                  </div>
                );
              })}
            </Space>
            <Divider style={{ margin: '8px 0' }} />
            <Row gutter={8}>
              <Col span={8}><Text type="secondary" style={{ fontSize: 12 }}>待安排 <Tag>{interviews.pending || 0}</Tag></Text></Col>
              <Col span={8}><Text type="secondary" style={{ fontSize: 12 }}>已安排 <Tag color="blue">{interviews.confirmed || 0}</Tag></Text></Col>
              <Col span={8}><Text type="secondary" style={{ fontSize: 12 }}>已完成 <Tag color="green">{interviews.completed || 0}</Tag></Text></Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {/* ═══ 招聘漏斗 ═══ */}
      <Card title="🔁 招聘漏斗" size="small" style={{ marginBottom: 24 }}>
        <Row gutter={[12, 12]} align="middle">
          <FunnelStep
            icon="📄"
            label="简历上传"
            value={resumes.total || 0}
            color="#94a3b8"
          />
          <FunnelStep
            icon="🏊"
            label="进入候选池"
            value={totalPool}
            color="#3b82f6"
          />
          <FunnelStep
            icon="📅"
            label="安排面试"
            value={interviews.confirmed || 0}
            color="#8b5cf6"
          />
          <FunnelStep
            icon="✅"
            label="面试完成"
            value={interviews.completed || 0}
            color="#10b981"
          />
          <FunnelStep
            icon="📧"
            label="发送 Offer"
            value={pipeline?.offers_sent || 0}
            color="#f59e0b"
          />
          <FunnelStep
            icon="🎉"
            label="已入职"
            value={pipeline?.onboarded || 0}
            color="#52c41a"
          />
        </Row>
        {totalPool > 0 && (
          <div style={{ marginTop: 12, textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              从候选池到面试完成转化率：
              <Text strong style={{ color: '#10b981', fontSize: 15, marginLeft: 4 }}>
                {Math.round((interviews.completed / Math.max(totalPool, 1)) * 100)}%
              </Text>
            </Text>
          </div>
        )}
      </Card>

      {/* ═══ 面试状态汇总 ═══ */}
      <Card title="📋 面试状态汇总" size="small">
        <Row gutter={16}>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title={<Text type="secondary" style={{ fontSize: 12 }}>⏳ 待安排</Text>}
                value={interviews.pending || 0}
                valueStyle={{ color: '#999', fontSize: 24 }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title={<Text type="secondary" style={{ fontSize: 12 }}>🔵 已安排</Text>}
                value={interviews.confirmed || 0}
                valueStyle={{ color: '#3b82f6', fontSize: 24 }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title={<Text type="secondary" style={{ fontSize: 12 }}>🟢 已完成</Text>}
                value={interviews.completed || 0}
                valueStyle={{ color: '#10b981', fontSize: 24 }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title={<Text type="secondary" style={{ fontSize: 12 }}>🎯 进行中</Text>}
                value={(interviews.confirmed || 0) + (interviews.pending || 0)}
                valueStyle={{ color: '#8b5cf6', fontSize: 24 }}
              />
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

/* ─── 子组件 ─── */

const ResumeBar: React.FC<{ label: string; color: string; count: number; total: number; icon: string }> = ({
  label, color, count, total, icon,
}) => {
  const pct = Math.round((count / total) * 100);
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
        <Text style={{ fontSize: 13 }}>{icon} {label}</Text>
        <Text strong style={{ fontSize: 13 }}>{count} 人（{pct}%）</Text>
      </div>
      <Progress
        percent={pct}
        showInfo={false}
        strokeColor={color === 'default' ? '#d9d9d9' : color}
        trailColor="#f5f5f5"
        size={['100%', 8]}
      />
    </div>
  );
};

const FunnelStep: React.FC<{ icon: string; label: string; value: number; color: string }> = ({
  icon, label, value, color,
}) => (
  <Col xs={12} md={4} style={{ textAlign: 'center' }}>
    <div style={{
      background: `linear-gradient(135deg, ${color}15, ${color}08)`,
      borderRadius: 12, padding: '16px 8px', border: `1px solid ${color}30`,
    }}>
      <div style={{ fontSize: 28, marginBottom: 4 }}>{icon}</div>
      <Text strong style={{ fontSize: 20, color }}>{value}</Text>
      <div><Text type="secondary" style={{ fontSize: 12 }}>{label}</Text></div>
    </div>
  </Col>
);

export default Dashboard;
