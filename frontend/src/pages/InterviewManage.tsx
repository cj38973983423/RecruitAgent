import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Typography, Table, Tag, Space, Button, Modal,
  Input, Select, message, Popconfirm, Tabs, Row, Col, Statistic,
  Slider, Segmented, Divider, DatePicker, Alert,
} from 'antd';
import type { Dayjs } from 'dayjs';
import {
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  LinkOutlined, TeamOutlined, ThunderboltOutlined, RobotOutlined,
  StarOutlined,
} from '@ant-design/icons';
import {
  createInterview, generateQuestions, evaluateInterview,
  listInterviewers, listResumes, deleteInterview, batchAction,
  listCandidates,
} from '../api';
import { EmptyGuide, stepIcons } from '../components/EmptyGuide';
import http from '../api';
import type { PipelineResponse, PipelineRound, Interviewer, Resume, Interview, InterviewCreatePayload, CandidateDetail } from '../types';

const { Title, Text } = Typography;
const { TextArea } = Input;

const ROUND_LABELS: Record<string, string> = {
  first: '一面', second: '二面', third: '三面', hr: 'HR面',
};
const ROUND_ORDER = ['first', 'second', 'third', 'hr'];

// 快速评分等级配置
const RATING_LEVELS = {
  excellent: { label: '🏆 优秀', tech: 90, comm: 90, overall: 90, color: '#52c41a', desc: '技能扎实，沟通流畅，非常满意' },
  good:      { label: '👍 良好', tech: 75, comm: 75, overall: 75, color: '#3b82f6', desc: '基本符合要求，建议通过' },
  average:   { label: '👌 一般', tech: 60, comm: 60, overall: 60, color: '#faad14', desc: '基础能力尚可，有提升空间' },
};

// ─── 面试管理页 ───

const InterviewManage: React.FC = () => {
  const [pipeline, setPipeline] = useState<PipelineRound[]>([]);
  const [loading, setLoading] = useState(false);
  const [tabKey, setTabKey] = useState('first');

  // 安排面试表单
  const [interviewers, setInterviewers] = useState<Interviewer[]>([]);
  const [candidates, setCandidates] = useState<CandidateDetail[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<number | undefined>(undefined);
  const [selectedInterviewer, setSelectedInterviewer] = useState<number | undefined>(undefined);
  const [selectedRound, setSelectedRound] = useState<string>('first');
  const [meetingLink, setMeetingLink] = useState('');
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number>(60);
  const [conflictWarnings, setConflictWarnings] = useState<string[]>([]);

  // 弹窗状态
  const [questionsModal, setQuestionsModal] = useState<any>(null);
  const [quickPassModal, setQuickPassModal] = useState<any>(null);  // {id, name, record}
  const [evalModal, setEvalModal] = useState<any>(null);
  const [aiDraftLoading, setAiDraftLoading] = useState(false);
  const [scheduleModal, setScheduleModal] = useState<any>(null);
  const [deptFilter, setDeptFilter] = useState<string>('all');

  const fetchPipeline = useCallback(async () => {
    setLoading(true);
    try {
      const res = await http.get('/interviews/pipeline').then(r => r.data as PipelineResponse);
      setPipeline(res?.pipeline ?? []);
    } catch {
      message.error('加载面试流水线失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchInterviewers = useCallback(async () => {
    try {
      const res = await listInterviewers({ status: 'active' });
      setInterviewers(Array.isArray(res) ? res : []);
    } catch { /* silent */ }
  }, []);

  const fetchCandidates = useCallback(async () => {
    try {
      const res = await listCandidates({ page_size: 100, status: 'manual_pass' });
      setCandidates(res?.items ?? []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchPipeline();
    fetchInterviewers();
    fetchCandidates();
  }, [fetchPipeline, fetchInterviewers, fetchCandidates]);

  const handleSchedule = async (values: any) => {
    try {
      setConflictWarnings([]);
      await createInterview(values);
      message.success('✅ 面试安排成功');
      setSelectedCandidate(undefined);
      setSelectedInterviewer(undefined);
      setSelectedRound('first');
      setMeetingLink('');
      setSelectedDate(null);
      setSelectedDuration(60);
      fetchPipeline();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message || '安排失败';
      if (err?.response?.status === 409) {
        setConflictWarnings(detail.replace(/时间冲突: /g, '').split('; '));
        message.warning('⛔ 存在时间冲突，请调整时间');
      } else {
        message.error('安排失败: ' + detail);
      }
    }
  };

  const handleGenerateQuestions = async (interviewId: number) => {
    try {
      const questions = await generateQuestions(interviewId);
      setQuestionsModal({ interviewId, questions });
      message.success(`已生成 ${questions.length} 道面试题`);
    } catch {
      message.error('生成面试题失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteInterview(id);
      message.success('🗑️ 面试已删除');
      fetchPipeline();
    } catch {
      message.error('删除失败');
    }
  };

  // ── 快速通过 ──
  const handleQuickPassSubmit = async () => {
    const { id, name, level, notes, evaluator } = quickPassModal;
    if (!level) { message.warning('请选择评价等级'); return; }
    try {
      const res = await http.post(`/interviews/${id}/quick-pass`, {
        rating_level: level, notes, evaluator: evaluator || undefined,
      }).then(r => r.data);
      const lvl = RATING_LEVELS[level as keyof typeof RATING_LEVELS];
      message.success(`✅ ${name} ${lvl?.label || ''}`);
      if (res.next_round_created) {
        message.success(`已自动进入${ROUND_LABELS[res.next_round]}等候池`);
        setTabKey(res.next_round as string);
      } else {
        message.success('🎉 全部面试完成！');
      }
      setQuickPassModal(null);
      fetchPipeline();
    } catch (e: any) {
      message.error('通过失败: ' + (e?.response?.data?.detail || e?.message));
    }
  };

  // ── 完整评价 ──
  const openEvalModal = (record: any) => {
    setEvalModal({
      id: record.id,
      candidate_name: record.candidate_name,
      tech_score: 70, project_score: 70, comm_score: 70,
      teamwork_score: 70, overall_score: 70,
      strengths: '', weaknesses: '', conclusion: '',
      recommendation: 'pass', evaluator: '',
    });
  };

  const handleEvaluateSubmit = async () => {
    const m = evalModal;
    if (!m.evaluator) { message.warning('请填写面试官'); return; }
    if (!m.recommendation) { message.warning('请选择评价结果'); return; }
    try {
      const res = await evaluateInterview(m.id, {
        evaluator: m.evaluator,
        tech_score: m.tech_score,
        communication_score: m.comm_score,
        overall_score: m.overall_score,
        strengths: m.strengths,
        weaknesses: m.weaknesses,
        conclusion: m.conclusion,
        recommendation: m.recommendation,
      });
      if (res.next_round_created) {
        message.success(`✅ 评价已提交，已进入${ROUND_LABELS[res.next_round]}等候池`);
        setTabKey(res.next_round as string);
      } else if (m.recommendation === 'pass') {
        message.success('🎉 全部面试完成！');
      } else {
        message.success('评价已提交');
      }
      setEvalModal(null);
      fetchPipeline();
    } catch (e: any) {
      const errMsg = e?.response?.data?.detail || e?.message || '未知错误';
      message.error('评价提交失败: ' + errMsg);
    }
  };

  // ── AI 辅助生成评价草稿 ──
  const handleAiDraft = async () => {
    if (!evalModal) return;
    setAiDraftLoading(true);
    try {
      const draft = await http.post(`/interviews/${evalModal.id}/ai-evaluation-draft`).then(r => r.data);
      setEvalModal((prev: any) => ({
        ...prev,
        tech_score: draft.tech_score ?? prev.tech_score,
        project_score: draft.project_score ?? prev.project_score,
        comm_score: draft.communication_score ?? prev.comm_score,
        teamwork_score: draft.teamwork_score ?? prev.teamwork_score,
        overall_score: draft.overall_score ?? prev.overall_score,
        strengths: draft.strengths || '',
        weaknesses: draft.weaknesses || '',
        conclusion: draft.conclusion || '',
        recommendation: draft.recommendation || prev.recommendation,
      }));
      message.success('🤖 AI 评价草稿已生成');
    } catch {
      message.error('AI 生成失败');
    } finally {
      setAiDraftLoading(false);
    }
  };

  // ── 弹窗安排面试 ──
  const handleScheduleFromModal = async () => {
    const m = scheduleModal;
    if (!m) return;
    if (!m.interviewer_id) { message.warning('请选择面试官'); return; }
    if (!m.date) { message.warning('请选择面试时间'); return; }
    const interviewer = interviewers.find(i => i.id === m.interviewer_id);
    try {
      setConflictWarnings([]);
      await createInterview({
        resume_id: m.resume_id,
        round: m.round,
        interviewer_name: interviewer?.name || '未知',
        interviewer_email: interviewer?.email || '',
        candidate_name: m.candidate_name,
        meeting_link: m.link,
        scheduled_at: m.date.toISOString(),
        duration_minutes: m.duration,
      });
      message.success(`✅ ${m.candidate_name} 面试安排成功`);
      setScheduleModal(null);
      fetchPipeline();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message || '安排失败';
      if (err?.response?.status === 409) {
        setConflictWarnings(detail.replace(/时间冲突: /g, '').split('; '));
        message.warning('⛔ 存在时间冲突，请调整时间');
      } else {
        message.error('安排失败: ' + detail);
      }
    }
  };

  // ── 加入候选人库（HR面通过后） ──
  const handleAddToPool = async (resumeId: number, name: string) => {
    try {
      await batchAction({ resume_ids: [resumeId], action: 'pass' });
      message.success(`🎉 ${name} 已加入候选人库，可在 Offer 管理中创建 Offer`);
      fetchPipeline();
    } catch (e: any) {
      message.error('操作失败: ' + (e?.response?.data?.detail || e?.message));
    }
  };

  const statusTag = (s: string) => {
    const cfg: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      pending:    { color: 'default',  icon: <ClockCircleOutlined />, label: '待安排' },
      confirmed:  { color: 'blue',     icon: <CheckCircleOutlined />, label: '已安排' },
      completed:  { color: 'green',    icon: <CheckCircleOutlined />, label: '已完成' },
      cancelled:  { color: 'red',      icon: <CloseCircleOutlined />, label: '已取消' },
    };
    const c = cfg[s] || { color: 'default', icon: null, label: s };
    return <Tag color={c.color}>{c.icon} {c.label}</Tag>;
  };

  const columns = [
    { title: '候选人', dataIndex: 'candidate_name', key: 'name', width: 90 },
    { title: '部门', dataIndex: 'department', key: 'dept', width: 80,
      render: (v: string) => v ? <Tag color="blue">{v}</Tag> : null },
    { title: '面试官', dataIndex: 'interviewer_name', key: 'interviewer', width: 100,
      render: (v: string) => v || <Text type="secondary">待分配</Text> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => statusTag(s) },
    { title: '面试链接', dataIndex: 'meeting_link', key: 'link', width: 180,
      render: (v: string) => v
        ? <Button type="link" size="small" href={v.startsWith('http') ? v : `https://${v}`}
            target="_blank" style={{ padding: 0 }}><LinkOutlined /> {v.slice(0, 25)}</Button>
        : <Text type="secondary">-</Text>,
    },
    { title: '时间', dataIndex: 'scheduled_at', key: 'time', width: 150,
      render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '待安排' },
    {
      title: '操作', key: 'action', width: 260,
      render: (_: any, record: any) => (
        <Space size="small" wrap>
          {record.status !== 'completed' && (
            <Button type="primary" size="small" icon={<ThunderboltOutlined />}
              onClick={() => setScheduleModal({
                resume_id: record.resume_id,
                candidate_name: record.candidate_name,
                round: record.round,
                interviewer_id: undefined,
                date: null,
                duration: 60,
                link: '',
              })}>
              📅 安排面试
            </Button>
          )}
          {record.status === 'confirmed' && (
            <>
              <Button type="link" size="small" style={{ color: '#52c41a' }}
                onClick={() => setQuickPassModal({
                  id: record.id,
                  name: record.candidate_name,
                  level: 'good',
                  notes: '',
                  evaluator: '',
                })}>
                ✅ 通过
              </Button>
              <Button type="link" size="small"
                onClick={() => openEvalModal(record)}>
                📊 评价
              </Button>
              <Button type="link" size="small" onClick={() => handleGenerateQuestions(record.id)}>
                ❓ 面试题
              </Button>
            </>
          )}
          {record.status === 'completed' && (
            record.round === 'first' ? (
              <Text type="secondary" style={{ fontSize: 12 }}>已评价</Text>
            ) : (
              <Popconfirm
                title={`将 ${record.candidate_name} 加入候选人库？`}
                description="加入后可在 Offer 管理中为其创建 Offer"
                onConfirm={() => handleAddToPool(record.resume_id, record.candidate_name)}
                okText="确认加入"
                cancelText="取消"
              >
                <Button type="primary" size="small" icon={<StarOutlined />}
                  style={{ background: '#722ed1', borderColor: '#722ed1' }}>
                  🏆 加入候选人库
                </Button>
              </Popconfirm>
            )
          )}
          <Popconfirm title={`删除「${record.candidate_name}」？`}
            onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button type="link" size="small" danger>🗑️</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const currentPipeline = pipeline.find(p => p.round === tabKey);
  const currentInterviews = currentPipeline?.interviews ?? [];

  // 所有部门列表
  const allDepts = [...new Set(
    pipeline.flatMap(p => p.interviews.map((iv: any) => iv.department).filter(Boolean))
  )] as string[];
  // 过滤
  const filteredInterviews = deptFilter === 'all'
    ? currentInterviews
    : currentInterviews.filter((iv: any) => iv.department === deptFilter);

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>📅 面试流程</Title>
        </Col>
        <Col>
          <Space size="middle">
            {pipeline.map(p => (
              <Statistic
                key={p.round}
                title={p.label}
                value={p.count}
                prefix={<TeamOutlined />}
                valueStyle={{ fontSize: 20, color: p.count > 0 ? '#3b82f6' : '#999' }}
              />
            ))}
          </Space>
        </Col>
      </Row>

      {/* 部门筛选 */}
      {allDepts.length > 1 && (
        <Card size="small" style={{ marginBottom: 12 }}>
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>部门：</Text>
            <Tag
              style={{ cursor: 'pointer' }}
              color={deptFilter === 'all' ? 'blue' : 'default'}
              onClick={() => setDeptFilter('all')}
            >全部</Tag>
            {allDepts.map(d => (
              <Tag
                key={d}
                style={{ cursor: 'pointer' }}
                color={deptFilter === d ? 'blue' : 'default'}
                onClick={() => setDeptFilter(d)}
              >{d}</Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 安排面试表单 */}
      <Card style={{ marginBottom: 16 }} styles={{ body: { padding: '12px 16px' } }}>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Text strong style={{ fontSize: 14 }}>安排新面试</Text>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8 }}>
            <Select
              placeholder="候选人（人工同意）"
              value={selectedCandidate}
              onChange={v => { setSelectedCandidate(v); setConflictWarnings([]); }}
              showSearch optionFilterProp="label" allowClear
              notFoundContent="暂无，请先完成简历筛选"
              options={candidates.map(c => ({
                value: c.id,
                label: `${c.name || '未知'}${c.department ? ` [${c.department}]` : ''}${c.jd_title ? ` · ${c.jd_title}` : ''}${c.ai_score != null ? ` (${c.ai_score}分)` : ''}`,
              }))}
            />
            <Select
              placeholder="面试官"
              value={selectedInterviewer}
              onChange={v => { setSelectedInterviewer(v); setConflictWarnings([]); }}
              showSearch optionFilterProp="label" allowClear
              options={interviewers.map(i => ({
                value: i.id,
                label: `${i.name}${i.position ? ` · ${i.position}` : ''}`,
              }))}
            />
            <Select
              placeholder="面试轮次"
              value={selectedRound}
              onChange={setSelectedRound}
              options={ROUND_ORDER.map(r => ({ value: r, label: ROUND_LABELS[r] }))}
            />
            <DatePicker
              showTime={{ format: 'HH:mm' }}
              format="MM/DD HH:mm"
              value={selectedDate}
              onChange={d => { setSelectedDate(d); setConflictWarnings([]); }}
              style={{ width: '100%' }}
              placeholder="选择日期时间"
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 2fr', gap: 8, alignItems: 'center' }}>
            <Select
              placeholder="时长(分)"
              value={selectedDuration}
              onChange={setSelectedDuration}
              options={[30, 45, 60, 90, 120].map(v => ({ value: v, label: `${v}分钟` }))}
            />
            <Input placeholder="面试链接" value={meetingLink}
              onChange={e => setMeetingLink(e.target.value)} />
            <div />
            <Button type="primary" onClick={() => {
              const interviewer = interviewers.find(i => i.id === selectedInterviewer);
              const candidate = candidates.find(c => c.id === selectedCandidate);
              if (!selectedCandidate) { message.warning('请选择候选人'); return; }
              if (!selectedInterviewer) { message.warning('请选择面试官'); return; }
              if (!selectedDate) { message.warning('请选择面试时间'); return; }
              handleSchedule({
                resume_id: selectedCandidate,
                round: selectedRound,
                interviewer_name: interviewer?.name || '未知',
                interviewer_email: interviewer?.email || '',
                candidate_name: candidate?.name || '未知',
                candidate_email: candidate?.email || '',
                meeting_link: meetingLink,
                scheduled_at: selectedDate.toISOString(),
                duration_minutes: selectedDuration,
              });
            }}>
              📅 安排面试
            </Button>
          </div>
          {/* 时间冲突警告 */}
          {conflictWarnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message="⛔ 时间冲突"
              description={conflictWarnings.map((w, i) => (
                <div key={i} style={{ marginTop: i > 0 ? 4 : 0 }}>• {w}</div>
              ))}
              closable
              onClose={() => setConflictWarnings([])}
            />
          )}
        </Space>
      </Card>

      {/* 流水线 Tab */}
      <Card>
        <Tabs
          activeKey={tabKey}
          onChange={setTabKey}
          items={pipeline.map(p => ({
            key: p.round,
            label: <span>{p.label} <Tag>{p.count}</Tag></span>,
            children: (
              <Table
                dataSource={filteredInterviews}
                columns={columns}
                rowKey="id"
                loading={loading}
                size="small"
                pagination={false}
                locale={{
                  emptyText: (
                    <EmptyGuide
                      title={`暂无${p.label}候选人`}
                      description="从简历管理中筛选候选人并安排面试"
                      steps={[
                        { icon: stepIcons.review, label: '简历管理筛选' },
                        { icon: stepIcons.interview, label: '选择面试官' },
                        { icon: stepIcons.schedule, label: '安排面试时间' },
                      ]}
                    />
                  ),
                }}
                expandable={{
                  expandedRowRender: (record: any) => {
                    const prevs = record.prev_evaluations;
                    if (!prevs || prevs.length === 0) {
                      return <Text type="secondary" style={{ fontSize: 12 }}>暂无前序轮次评价记录</Text>;
                    }
                    const recMap: Record<string, string> = {
                      pass: '✅ 通过', hold: '⏳ 待定', reject: '❌ 淘汰',
                    };
                    const roundColors: Record<string, string> = {
                      first: '#3b82f6', second: '#8b5cf6', third: '#f59e0b', hr: '#10b981',
                    };
                    return (
                      <div style={{ padding: '8px 0 8px 40px' }}>
                        <Space direction="vertical" size={8} style={{ width: '100%' }}>
                          {prevs.map((prev: any, idx: number) => (
                            <div key={idx} style={{
                              background: '#fafafa', borderRadius: 6, padding: '10px 14px',
                              borderLeft: `3px solid ${roundColors[prev.round] || '#999'}`,
                            }}>
                              <Text strong style={{ fontSize: 13, color: roundColors[prev.round] || '#8b5cf6' }}>
                                📋 {prev.round_label} 评价
                              </Text>
                              <div style={{ display: 'flex', gap: 20, marginTop: 4, flexWrap: 'wrap' }}>
                                <div><Text type="secondary" style={{ fontSize: 12 }}>评价人:</Text>
                                  <Text style={{ fontSize: 12, marginLeft: 4 }}>{prev.evaluator || '系统自动'}</Text></div>
                                <div><Text type="secondary" style={{ fontSize: 12 }}>技术:</Text>
                                  <Text style={{ fontSize: 12, marginLeft: 4, fontWeight: 600, color: prev.tech_score >= 70 ? '#52c41a' : '#faad14' }}>{prev.tech_score}</Text></div>
                                <div><Text type="secondary" style={{ fontSize: 12 }}>沟通:</Text>
                                  <Text style={{ fontSize: 12, marginLeft: 4, fontWeight: 600, color: prev.communication_score >= 70 ? '#52c41a' : '#faad14' }}>{prev.communication_score}</Text></div>
                                <div><Text type="secondary" style={{ fontSize: 12 }}>综合:</Text>
                                  <Text style={{ fontSize: 12, marginLeft: 4, fontWeight: 600, color: '#8b5cf6' }}>{prev.overall_score}</Text></div>
                                <div><Text type="secondary" style={{ fontSize: 12 }}>结果:</Text>
                                  <Text style={{ fontSize: 12, marginLeft: 4 }}>{recMap[prev.recommendation] || prev.recommendation}</Text></div>
                              </div>
                              {prev.strengths && <Text style={{ fontSize: 12, display: 'block', marginTop: 2 }}>💪 优势：{prev.strengths}</Text>}
                              {prev.weaknesses && <Text style={{ fontSize: 12, display: 'block' }}>⚠️ 待提升：{prev.weaknesses}</Text>}
                              {prev.conclusion && <Text style={{ fontSize: 12, display: 'block' }}>📝 结论：{prev.conclusion}</Text>}
                            </div>
                          ))}
                        </Space>
                      </div>
                    );
                  },
                  rowExpandable: (record: any) => !!(record.prev_evaluations?.length),
                }}
              />
            ),
          }))}
          style={{ marginTop: -8 }}
        />
      </Card>

      {/* ═══ 安排面试弹窗 ═══ */}
      <Modal
        title={`📅 安排面试 - ${scheduleModal?.candidate_name || ''}`}
        open={!!scheduleModal}
        onCancel={() => setScheduleModal(null)}
        onOk={handleScheduleFromModal}
        okText="确认安排"
        width={520}
      >
        {scheduleModal && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text type="secondary">候选人</Text>
              <Input value={scheduleModal.candidate_name} disabled />
            </div>
            <div>
              <Text type="secondary">面试轮次</Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                value={scheduleModal.round}
                onChange={v => setScheduleModal({ ...scheduleModal, round: v })}
                options={ROUND_ORDER.map(r => ({ value: r, label: ROUND_LABELS[r] }))}
              />
            </div>
            <div>
              <Text type="secondary">面试官</Text>
              <Select
                style={{ width: '100%', marginTop: 4 }}
                placeholder="选择面试官"
                value={scheduleModal.interviewer_id}
                onChange={v => setScheduleModal({ ...scheduleModal, interviewer_id: v })}
                showSearch optionFilterProp="label"
                options={interviewers.map(i => ({
                  value: i.id,
                  label: `${i.name}${i.position ? ` · ${i.position}` : ''}`,
                }))}
              />
            </div>
            <Row gutter={12}>
              <Col span={14}>
                <Text type="secondary">面试时间</Text>
                <DatePicker
                  showTime={{ format: 'HH:mm' }}
                  format="MM/DD HH:mm"
                  style={{ width: '100%', marginTop: 4 }}
                  value={scheduleModal.date}
                  onChange={d => setScheduleModal({ ...scheduleModal, date: d })}
                  placeholder="选择日期时间"
                />
              </Col>
              <Col span={10}>
                <Text type="secondary">时长</Text>
                <Select
                  style={{ width: '100%', marginTop: 4 }}
                  value={scheduleModal.duration}
                  onChange={v => setScheduleModal({ ...scheduleModal, duration: v })}
                  options={[30, 45, 60, 90, 120].map(v => ({ value: v, label: `${v}分钟` }))}
                />
              </Col>
            </Row>
            <div>
              <Text type="secondary">面试链接</Text>
              <Input
                style={{ marginTop: 4 }}
                placeholder="如：https://meeting.tencent.com/xxx"
                value={scheduleModal.link}
                onChange={e => setScheduleModal({ ...scheduleModal, link: e.target.value })}
              />
            </div>
          </Space>
        )}
      </Modal>

      {/* 面试题弹窗 */}
      <Modal title="❓ AI 生成面试题" open={!!questionsModal}
        onCancel={() => setQuestionsModal(null)} footer={null} width={700}>
        {questionsModal?.questions?.map((q: any, i: number) => (
          <Card key={i} size="small" style={{ marginBottom: 12 }}>
            <Space style={{ marginBottom: 8 }}>
              <Tag color={q.category === 'tech' ? 'blue' : q.category === 'project' ? 'green' : q.category === 'scene' ? 'orange' : 'purple'}>
                {q.category}
              </Tag>
              <Tag>{q.difficulty}</Tag>
            </Space>
            <div><Text strong>Q{i + 1}: {q.question}</Text></div>
            {q.reason && <Text type="secondary" style={{ fontSize: 12 }}>💡 {q.reason}</Text>}
            {q.expected_answer && (
              <div style={{ marginTop: 8, background: '#f6ffed', padding: '8px 12px', borderRadius: 6 }}>
                <Text style={{ fontSize: 12, color: '#52c41a' }}>📝 {q.expected_answer}</Text>
              </div>
            )}
          </Card>
        ))}
      </Modal>

      {/* ═══ 快速通过弹窗 ═══ */}
      <Modal
        title={`✅ 快速通过 - ${quickPassModal?.name || ''}`}
        open={!!quickPassModal}
        onCancel={() => setQuickPassModal(null)}
        onOk={handleQuickPassSubmit}
        okText="确认通过"
        width={480}
      >
        {quickPassModal && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {/* 评分等级 */}
            <div>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>评分等级</Text>
              <Segmented
                value={quickPassModal.level}
                onChange={(v) => setQuickPassModal({ ...quickPassModal, level: v as string })}
                style={{ width: '100%' }}
                options={Object.entries(RATING_LEVELS).map(([k, v]) => ({
                  value: k,
                  label: <span style={{ color: v.color }}>{v.label}</span>,
                }))}
              />
            </div>

            {/* 评分预览 */}
            {(() => {
              const lvl = RATING_LEVELS[quickPassModal.level as keyof typeof RATING_LEVELS];
              if (!lvl) return null;
              return (
                <div style={{ background: '#f9fafb', borderRadius: 8, padding: '12px 16px' }}>
                  <Row gutter={16}>
                    <Col span={8}><Text type="secondary" style={{ fontSize: 12 }}>技术</Text><br /><Text strong style={{ color: lvl.color }}>{lvl.tech}</Text></Col>
                    <Col span={8}><Text type="secondary" style={{ fontSize: 12 }}>沟通</Text><br /><Text strong style={{ color: lvl.color }}>{lvl.comm}</Text></Col>
                    <Col span={8}><Text type="secondary" style={{ fontSize: 12 }}>综合</Text><br /><Text strong style={{ color: lvl.color }}>{lvl.overall}</Text></Col>
                  </Row>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>{lvl.desc}</Text>
                </div>
              );
            })()}

            {/* 面试官 + 备注 */}
            <Input
              placeholder="面试官姓名（可选）"
              value={quickPassModal.evaluator}
              onChange={e => setQuickPassModal({ ...quickPassModal, evaluator: e.target.value })}
            />
            <TextArea
              rows={2}
              placeholder="备注（可选，如：面试表现很好，技术基础扎实）"
              value={quickPassModal.notes}
              onChange={e => setQuickPassModal({ ...quickPassModal, notes: e.target.value })}
            />
          </Space>
        )}
      </Modal>

      {/* ═══ 完整评价弹窗 ═══ */}
      <Modal
        title={`📊 面试评价 - ${evalModal?.candidate_name || ''}`}
        open={!!evalModal}
        onCancel={() => setEvalModal(null)}
        onOk={handleEvaluateSubmit}
        okText="提交评价"
        width={600}
      >
        {evalModal && (
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {/* AI 辅助按钮 */}
            <Button
              type="dashed"
              icon={<RobotOutlined />}
              onClick={handleAiDraft}
              loading={aiDraftLoading}
              block
            >
              🤖 AI 辅助生成评价草稿
            </Button>
            <Divider style={{ margin: '8px 0' }} />

            {/* 面试官 */}
            <Input
              placeholder="面试官姓名"
              value={evalModal.evaluator}
              onChange={e => setEvalModal({ ...evalModal, evaluator: e.target.value })}
            />

            {/* 多维度评分滑块 */}
            <div>
              <Text strong style={{ fontSize: 13 }}>多维度评分</Text>
              <div style={{ marginTop: 8 }}>
                <ScoreSlider label="🔧 技术深度" value={evalModal.tech_score}
                  onChange={v => setEvalModal({ ...evalModal, tech_score: v })} />
                <ScoreSlider label="🏗️ 项目经验" value={evalModal.project_score}
                  onChange={v => setEvalModal({ ...evalModal, project_score: v })} />
                <ScoreSlider label="💬 沟通表达" value={evalModal.comm_score}
                  onChange={v => setEvalModal({ ...evalModal, comm_score: v })} />
                <ScoreSlider label="🤝 团队协作" value={evalModal.teamwork_score}
                  onChange={v => setEvalModal({ ...evalModal, teamwork_score: v })} />
                <Divider style={{ margin: '6px 0' }} />
                <ScoreSlider label="📊 综合评分" value={evalModal.overall_score}
                  onChange={v => setEvalModal({ ...evalModal, overall_score: v })} color="#8b5cf6" />
              </div>
            </div>

            {/* 文本评价 */}
            <TextArea rows={2} placeholder="优势" value={evalModal.strengths}
              onChange={e => setEvalModal({ ...evalModal, strengths: e.target.value })} />
            <TextArea rows={2} placeholder="待提升项" value={evalModal.weaknesses}
              onChange={e => setEvalModal({ ...evalModal, weaknesses: e.target.value })} />
            <TextArea rows={2} placeholder="面试结论" value={evalModal.conclusion}
              onChange={e => setEvalModal({ ...evalModal, conclusion: e.target.value })} />

            {/* 评价结果 */}
            <div>
              <Text strong>评价结果：</Text>
              <Space style={{ marginTop: 4 }}>
                {[
                  { value: 'pass', label: '✅ 通过（进入下一轮）', color: '#52c41a' },
                  { value: 'hold', label: '⏳ 待定', color: '#faad14' },
                  { value: 'reject', label: '❌ 淘汰（流程终止）', color: '#ff4d4f' },
                ].map(r => (
                  <Button
                    key={r.value}
                    size="small"
                    type={evalModal.recommendation === r.value ? 'primary' : 'default'}
                    style={evalModal.recommendation === r.value ? { background: r.color, borderColor: r.color } : {}}
                    onClick={() => setEvalModal({ ...evalModal, recommendation: r.value })}
                  >
                    {r.label}
                  </Button>
                ))}
              </Space>
            </div>
          </Space>
        )}
      </Modal>
    </div>
  );
};

// ─── 评分滑块组件 ───

const ScoreSlider: React.FC<{
  label: string; value: number; onChange: (v: number) => void; color?: string;
}> = ({ label, value, onChange, color }) => {
  const getColor = (v: number) => {
    if (color) return color;
    if (v >= 80) return '#52c41a';
    if (v >= 60) return '#3b82f6';
    if (v >= 40) return '#faad14';
    return '#ff4d4f';
  };
  const getLabel = (v: number) => {
    if (v >= 85) return '优秀';
    if (v >= 70) return '良好';
    if (v >= 55) return '一般';
    if (v >= 40) return '较差';
    return '不及格';
  };
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 12 }}>{label}</Text>
        <Text style={{ fontSize: 12, color: getColor(value), fontWeight: 600 }}>
          {value} 分 · {getLabel(value)}
        </Text>
      </div>
      <Slider
        min={0} max={100} value={value}
        onChange={onChange}
        trackStyle={{ background: getColor(value) }}
        handleStyle={{ borderColor: getColor(value) }}
      />
    </div>
  );
};

export default InterviewManage;
