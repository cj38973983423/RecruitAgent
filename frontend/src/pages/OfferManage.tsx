import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Typography, Table, Tag, Space, Button, Modal, Input,
  Select, message, Popconfirm, Tabs, Row, Col, Statistic,
  Divider, DatePicker, Empty, Tooltip,
} from 'antd';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import {
  SendOutlined, CheckCircleOutlined, CloseCircleOutlined,
  RollbackOutlined, DeleteOutlined, PlusOutlined,
  ClockCircleOutlined, TeamOutlined, DollarOutlined,
  FileTextOutlined, UserOutlined,
} from '@ant-design/icons';
import {
  listOffers, createOffer, sendOffer, acceptOffer, rejectOffer,
  withdrawOffer, deleteOffer, listApprovedJDs, listCandidates,
} from '../api';
import { EmptyGuide, stepIcons } from '../components/EmptyGuide';
import type { Offer, OfferStatus, JobDescription, CandidateDetail } from '../types';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const STATUS_CONFIG: Record<OfferStatus, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  sent: { label: '已发送', color: 'blue' },
  accepted: { label: '已接受', color: 'green' },
  rejected: { label: '已拒绝', color: 'red' },
  withdrawn: { label: '已撤回', color: 'orange' },
  onboarded: { label: '已入职', color: 'purple' },
};

const OfferManage: React.FC = () => {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(false);
  const [tabKey, setTabKey] = useState<string>('all');

  // 新建 Offer 弹窗
  const [createModal, setCreateModal] = useState(false);
  const [candidates, setCandidates] = useState<CandidateDetail[]>([]);
  const [jdList, setJdList] = useState<JobDescription[]>([]);
  const [newOffer, setNewOffer] = useState({
    resume_id: undefined as number | undefined,
    jd_id: undefined as number | undefined,
    candidate_name: '',
    position_name: '',
    department: '',
    salary: '',
    equity: '',
    start_date: null as Dayjs | null,
    notes: '',
  });
  const [creating, setCreating] = useState(false);

  // 操作弹窗
  const [actionModal, setActionModal] = useState<{ offer: Offer; action: string } | null>(null);
  const [actionValue, setActionValue] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const fetchOffers = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {};
      if (tabKey !== 'all') params.status = tabKey;
      const data = await listOffers(params);
      setOffers(Array.isArray(data) ? data : []);
    } catch {
      message.error('加载 Offer 列表失败');
    } finally {
      setLoading(false);
    }
  }, [tabKey]);

  const fetchMeta = useCallback(async () => {
    try {
      const [jdData, candidateResp] = await Promise.all([
        listApprovedJDs(),
        listCandidates({ page_size: 200, status: 'no_offer' }),
      ]);
      // listApprovedJDs 可能返回 {groups: {...}} 格式
      if (jdData && typeof jdData === 'object' && !Array.isArray(jdData) && (jdData as any).groups) {
        // 从分组中提取所有 JD
        const allJds: JobDescription[] = [];
        for (const dept of Object.keys((jdData as any).groups)) {
          for (const jd of (jdData as any).groups[dept]) {
            allJds.push({ ...jd, department: dept });
          }
        }
        setJdList(allJds);
      } else {
        setJdList(Array.isArray(jdData) ? jdData : []);
      }
      setCandidates(candidateResp?.items ?? []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchOffers(); }, [fetchOffers]);
  useEffect(() => { fetchMeta(); }, [fetchMeta]);

  // ── 新建 Offer ──
  const handleCreate = async () => {
    if (!newOffer.candidate_name || !newOffer.salary) {
      message.warning('请填写候选人姓名和薪资');
      return;
    }
    setCreating(true);
    try {
      await createOffer({
        resume_id: newOffer.resume_id,
        jd_id: newOffer.jd_id,
        candidate_name: newOffer.candidate_name,
        position_name: newOffer.position_name || '待定',
        department: newOffer.department || '待定',
        salary: newOffer.salary,
        equity: newOffer.equity || undefined,
        start_date: newOffer.start_date?.toISOString(),
        notes: newOffer.notes || undefined,
      });
      message.success('✅ Offer 创建成功');
      setCreateModal(false);
      setNewOffer({
        resume_id: undefined, jd_id: undefined,
        candidate_name: '', position_name: '', department: '',
        salary: '', equity: '', start_date: null, notes: '',
      });
      fetchOffers();
    } catch (err: any) {
      message.error('创建失败: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setCreating(false);
    }
  };

  // ── 操作：发送/接受/拒绝/撤回 ──
  const handleAction = async () => {
    if (!actionModal) return;
    setActionLoading(true);
    const { offer, action } = actionModal;
    try {
      if (action === 'send') {
        await sendOffer(offer.id, actionValue || undefined);
        message.success(`📧 Offer 已发送给 ${offer.candidate_name}`);
      } else if (action === 'accept') {
        await acceptOffer(offer.id, actionValue || undefined);
        message.success(`🎉 ${offer.candidate_name} 已接受 Offer`);
      } else if (action === 'reject') {
        await rejectOffer(offer.id, actionValue || undefined);
        message.info(`😢 ${offer.candidate_name} 已拒绝 Offer`);
      } else if (action === 'withdraw') {
        await withdrawOffer(offer.id);
        message.warning('↩️ Offer 已撤回');
      }
      setActionModal(null);
      setActionValue('');
      fetchOffers();
    } catch (err: any) {
      message.error('操作失败: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  // ── 候选人在选择后自动填充 ──
  const handleSelectCandidate = (resumeId: number) => {
    const candidate = candidates.find(c => c.id === resumeId);
    if (candidate) {
      setNewOffer(prev => ({
        ...prev,
        resume_id: resumeId,
        candidate_name: candidate.name || '',
        position_name: candidate.jd_title || '',
        department: candidate.department || '',
      }));
    }
  };

  // ── 表格列 ──
  const columns = [
    {
      title: '候选人', dataIndex: 'candidate_name', key: 'name',
      width: 120,
      render: (v: string, r: Offer) => (
        <Space>
          <UserOutlined />
          <Text strong>{v}</Text>
        </Space>
      ),
    },
    { title: '职位', dataIndex: 'position_name', key: 'pos', width: 160, ellipsis: true },
    { title: '部门', dataIndex: 'department', key: 'dept', width: 100 },
    {
      title: '薪资', dataIndex: 'salary', key: 'salary', width: 140,
      render: (v: string) => <Text><DollarOutlined /> {v}</Text>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (v: OfferStatus) => {
        const cfg = STATUS_CONFIG[v] || { label: v, color: 'default' };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '操作', key: 'action', width: 300, fixed: 'right' as const,
      render: (_: unknown, record: Offer) => {
        const actions: React.ReactNode[] = [];

        if (record.status === 'draft') {
          actions.push(
            <Button key="send" type="primary" size="small" icon={<SendOutlined />}
              onClick={() => { setActionModal({ offer: record, action: 'send' }); setActionValue(''); }}>
              发送
            </Button>,
          );
        } else if (record.status === 'sent') {
          actions.push(
            <Button key="accept" type="primary" size="small" icon={<CheckCircleOutlined />}
              style={{ background: '#52c41a', borderColor: '#52c41a' }}
              onClick={() => { setActionModal({ offer: record, action: 'accept' }); setActionValue(''); }}>
              接受
            </Button>,
            <Button key="reject" danger size="small" icon={<CloseCircleOutlined />}
              onClick={() => { setActionModal({ offer: record, action: 'reject' }); setActionValue(''); }}>
              拒绝
            </Button>,
            <Button key="withdraw" size="small" icon={<RollbackOutlined />}
              onClick={() => { setActionModal({ offer: record, action: 'withdraw' }); }}>
              撤回
            </Button>,
          );
        }

        // 所有状态都显示删除按钮
        actions.push(
          <Popconfirm key="delete" title="确定删除此 Offer？"
            description="此操作不可撤销"
            onConfirm={() => deleteOffer(record.id).then(() => { message.success('已删除'); fetchOffers(); })}>
            <Button danger size="small" icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>,
        );

        return <Space size={4}>{actions}</Space>;
      },
    },
  ];

  // ── 统计数据 ──
  const stats = {
    draft: offers.filter(o => o.status === 'draft').length,
    sent: offers.filter(o => o.status === 'sent').length,
    accepted: offers.filter(o => o.status === 'accepted').length,
    onboarded: offers.filter(o => o.status === 'onboarded').length,
    rejected: offers.filter(o => o.status === 'rejected').length,
  };

  const filtered = tabKey === 'all' ? offers : offers.filter(o => o.status === tabKey);

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}><Card size="small"><Statistic title="全部" value={offers.length} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="草稿" value={stats.draft} valueStyle={{ color: '#8c8c8c' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="已发送" value={stats.sent} valueStyle={{ color: '#3b82f6' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="已接受" value={stats.accepted} valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="已入职" value={stats.onboarded} valueStyle={{ color: '#722ed1' }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="已拒绝" value={stats.rejected} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
      </Row>

      <Card
        title={<Space><FileTextOutlined /> Offer 管理</Space>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>
            新建 Offer
          </Button>
        }
      >
        <Tabs activeKey={tabKey} onChange={setTabKey}
          items={[
            { key: 'all', label: '全部' },
            { key: 'draft', label: '草稿' },
            { key: 'sent', label: '已发送' },
            { key: 'accepted', label: '已接受' },
            { key: 'onboarded', label: '已入职' },
            { key: 'rejected', label: '已拒绝' },
          ]}
        />

        {filtered.length === 0 ? (
          <Empty description={
            <Space direction="vertical" style={{ textAlign: 'center' }}>
              <Text type="secondary">暂无 Offer</Text>
              <Button type="primary" ghost onClick={() => setCreateModal(true)}>➕ 新建第一个 Offer</Button>
            </Space>
          } />
        ) : (
          <Table dataSource={filtered} columns={columns}
            rowKey="id" size="small" loading={loading}
            scroll={{ x: 1000 }}
            expandable={{
              expandedRowRender: (r: Offer) => (
                <div style={{ padding: '8px 0' }}>
                  <Row gutter={16}>
                    <Col span={6}><Text type="secondary">股权：</Text>{r.equity || '-'}</Col>
                    <Col span={6}><Text type="secondary">入职日期：</Text>{r.start_date ? dayjs(r.start_date).format('YYYY-MM-DD') : '-'}</Col>
                    <Col span={6}><Text type="secondary">发送时间：</Text>{r.sent_at ? dayjs(r.sent_at).format('MM-DD HH:mm') : '-'}</Col>
                    <Col span={6}>
                      {r.status === 'accepted' && <><Text type="secondary">接受时间：</Text>{r.accepted_at ? dayjs(r.accepted_at).format('MM-DD HH:mm') : '-'}</>}
                      {r.status === 'rejected' && <><Text type="secondary">拒绝时间：</Text>{r.rejected_at ? dayjs(r.rejected_at).format('MM-DD HH:mm') : '-'}</>}
                    </Col>
                  </Row>
                  {r.notes && <div style={{ marginTop: 8 }}><Text type="secondary">备注：</Text>{r.notes}</div>}
                </div>
              ),
            }}
          />
        )}
      </Card>

      {/* ── 新建 Offer 弹窗 ── */}
      <Modal title={<Space><PlusOutlined /> 新建 Offer</Space>}
        open={createModal} onOk={handleCreate} onCancel={() => setCreateModal(false)}
        confirmLoading={creating} okText="创建" cancelText="取消" width={600}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>从候选池选择</Text>
            <Select showSearch placeholder="搜索候选人姓名..." style={{ width: '100%' }}
              value={newOffer.resume_id} onChange={handleSelectCandidate}
              filterOption={(input, option) => (option?.label as string || '').includes(input)}
              options={candidates.map(c => ({
                value: c.id,
                label: `${c.name || '未知'} ${c.department ? `[${c.department}]` : ''} ${c.jd_title ? `· ${c.jd_title}` : ''} ${c.ai_score != null ? `(${c.ai_score}分)` : ''}`,
              }))}
              allowClear
            />
          </div>
          <Divider style={{ margin: '8px 0' }} />
          <Row gutter={12}>
            <Col span={12}>
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">候选人姓名 *</Text>
                <Input value={newOffer.candidate_name}
                  onChange={e => setNewOffer(p => ({ ...p, candidate_name: e.target.value }))}
                  placeholder="输入姓名" />
              </div>
            </Col>
            <Col span={6}>
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">部门</Text>
                <Select placeholder="选择或输入部门"
                  value={newOffer.department || undefined}
                  onChange={v => setNewOffer(p => ({ ...p, department: v }))}
                  style={{ width: '100%' }}
                  showSearch
                  allowClear
                  filterOption={(input, option) => (option?.label as string || '').includes(input)}
                  options={Array.from(new Set(jdList.map(j => j.department).filter(Boolean))).map(d => ({
                    value: d!,
                    label: d!,
                  }))}
                />
              </div>
            </Col>
            <Col span={6}>
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">职位名称</Text>
                <Input value={newOffer.position_name}
                  onChange={e => setNewOffer(p => ({ ...p, position_name: e.target.value }))}
                  placeholder="如：高级Python工程师" />
              </div>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Text type="secondary">薪资方案 *</Text>
              <Input value={newOffer.salary}
                onChange={e => setNewOffer(p => ({ ...p, salary: e.target.value }))}
                placeholder="如：30K-50K/月" />
            </Col>
            <Col span={12}>
              <Text type="secondary">股权/期权</Text>
              <Input value={newOffer.equity}
                onChange={e => setNewOffer(p => ({ ...p, equity: e.target.value }))}
                placeholder="如：1% 期权（可选）" />
            </Col>
          </Row>
          <div>
            <Text type="secondary">预期入职日期</Text>
            <DatePicker style={{ width: '100%' }}
              value={newOffer.start_date}
              onChange={d => setNewOffer(p => ({ ...p, start_date: d }))} />
          </div>
          <div>
            <Text type="secondary">备注</Text>
            <TextArea rows={3} value={newOffer.notes}
              onChange={e => setNewOffer(p => ({ ...p, notes: e.target.value }))}
              placeholder="额外说明..." />
          </div>
        </Space>
      </Modal>

      {/* ── 操作弹窗（发送/接受/拒绝） ── */}
      <Modal
        title={
          actionModal?.action === 'send' ? '📧 发送 Offer' :
          actionModal?.action === 'accept' ? '🎉 接受 Offer' :
          actionModal?.action === 'reject' ? '😢 拒绝 Offer' : '↩️ 撤回 Offer'
        }
        open={!!actionModal}
        onOk={handleAction}
        onCancel={() => { setActionModal(null); setActionValue(''); }}
        confirmLoading={actionLoading}
        okText={
          actionModal?.action === 'send' ? '确认发送' :
          actionModal?.action === 'accept' ? '确认接受' :
          actionModal?.action === 'reject' ? '确认拒绝' : '确认撤回'
        }
        okButtonProps={{
          danger: actionModal?.action === 'reject' || actionModal?.action === 'withdraw',
          style: actionModal?.action === 'accept' ? { background: '#52c41a', borderColor: '#52c41a' } : undefined,
        }}
      >
        {actionModal?.action === 'send' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>即将向 <Text strong>{actionModal.offer.candidate_name}</Text> 发送 Offer</Text>
            <div><Text type="secondary">入职日期（可选）</Text>
              <DatePicker style={{ width: '100%' }}
                onChange={d => setActionValue(d?.toISOString() || '')} />
            </div>
          </Space>
        )}
        {actionModal?.action === 'accept' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>确认 <Text strong>{actionModal.offer.candidate_name}</Text> 接受此 Offer？</Text>
            <div><Text type="secondary">实际入职日期（可选）</Text>
              <DatePicker style={{ width: '100%' }}
                onChange={d => setActionValue(d?.toISOString() || '')} />
            </div>
          </Space>
        )}
        {actionModal?.action === 'reject' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>确认 <Text strong>{actionModal.offer.candidate_name}</Text> 拒绝此 Offer？</Text>
            <TextArea rows={3} placeholder="拒绝原因（可选）"
              value={actionValue} onChange={e => setActionValue(e.target.value)} />
          </Space>
        )}
        {actionModal?.action === 'withdraw' && (
          <Text>确定撤回给 <Text strong>{actionModal?.offer.candidate_name}</Text> 的 Offer？</Text>
        )}
      </Modal>
    </div>
  );
};

export default OfferManage;
