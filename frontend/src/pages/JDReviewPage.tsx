import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Card, Typography, Button, Tag, Space, Spin, message, Modal,
  Collapse, Divider, Empty, Alert, Input,
  Row, Col, Statistic, Tooltip,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, EyeOutlined,
  ApartmentOutlined, TeamOutlined, ReloadOutlined, LoadingOutlined,
  SaveOutlined, EditOutlined,
} from '@ant-design/icons';
import { listPendingJDs, approvePendingJD, rejectPendingJD, regenerateJD, saveJDContent } from '../api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

const JDReviewPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [rejectModal, setRejectModal] = useState<any>(null);
  const [rejectReason, setRejectReason] = useState('');

  const [regenerateModal, setRegenerateModal] = useState<any>(null);
  const [regenerateHints, setRegenerateHints] = useState('');

  // 编辑状态：记录每个 JD 是否在编辑 + 编辑内容
  const [editing, setEditing] = useState<Record<number, boolean>>({});
  const [editContent, setEditContent] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<Record<number, boolean>>({});

  const timerRef = useRef<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await listPendingJDs();
      setData(result);
      const hasRegenerating = Object.values(result.groups || {}).some((jds: any) =>
        jds.some((j: any) => j.status === 'regenerating')
      );
      if (!hasRegenerating && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  const checkAndPoll = useCallback(() => {
    if (!data) return;
    const hasRegenerating = Object.values(data.groups || {}).some((jds: any) =>
      jds.some((j: any) => j.status === 'regenerating')
    );
    if (hasRegenerating && !timerRef.current) {
      timerRef.current = window.setInterval(loadData, 3000);
    }
  }, [data, loadData]);

  useEffect(() => { loadData(); return () => { if (timerRef.current) clearInterval(timerRef.current); }; }, [loadData]);
  useEffect(() => { if (!loading && data) checkAndPoll(); }, [data, loading, checkAndPoll]);

  const handleApprove = async (jd: any) => {
    setActionLoading(jd.id);
    try {
      await approvePendingJD(jd.id);
      message.success(`✅ 「${jd.title}」已审核通过！`);
      loadData();
    } catch (err: any) {
      message.error('审批失败: ' + (err?.response?.data?.detail || err.message));
    } finally { setActionLoading(null); }
  };

  const handleReject = async () => {
    if (!rejectModal) return;
    setActionLoading(rejectModal.id);
    try {
      await rejectPendingJD(rejectModal.id, rejectReason);
      message.warning(`❌ 「${rejectModal.title}」已驳回`);
      setRejectModal(null);
      setRejectReason('');
      loadData();
    } catch (err: any) {
      message.error('驳回失败: ' + (err?.response?.data?.detail || err.message));
    } finally { setActionLoading(null); }
  };

  const handleRegenerate = async () => {
    if (!regenerateModal) return;
    setActionLoading(regenerateModal.id);
    try {
      const result = await regenerateJD(regenerateModal.id, regenerateHints);
      message.info(result.message);
      setRegenerateModal(null);
      setRegenerateHints('');
      loadData();
    } catch (err: any) {
      message.error('重新生成失败: ' + (err?.response?.data?.detail || err.message));
    } finally { setActionLoading(null); }
  };

  /** 开始编辑 JD */
  const startEdit = (jd: any) => {
    setEditing(prev => ({ ...prev, [jd.id]: true }));
    setEditContent(prev => ({ ...prev, [jd.id]: jd.content }));
  };

  /** 取消编辑 */
  const cancelEdit = (jdId: number) => {
    setEditing(prev => ({ ...prev, [jdId]: false }));
    setEditContent(prev => { const n = { ...prev }; delete n[jdId]; return n; });
  };

  /** 保存编辑内容 */
  const handleSave = async (jdId: number) => {
    const content = editContent[jdId];
    if (!content || !content.trim()) {
      message.warning('内容不能为空');
      return;
    }
    setSaving(prev => ({ ...prev, [jdId]: true }));
    try {
      await saveJDContent(jdId, content);
      message.success('✅ JD 内容已保存');
      cancelEdit(jdId);
      loadData();
    } catch (err: any) {
      message.error('保存失败: ' + (err?.response?.data?.detail || err.message));
    } finally { setSaving(prev => ({ ...prev, [jdId]: false })); }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;

  const groups = data?.groups || {};
  const departments = data?.departments || [];
  const allJds = Object.values(groups).flat() as any[];
  const total = allJds.length;
  const regeneratingCount = allJds.filter((j: any) => j.status === 'regenerating').length;
  const pendingCount = allJds.filter((j: any) => j.status === 'pending_review').length;

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="待处理" value={total} suffix="个" valueStyle={{ color: '#faad14' }} prefix={<EyeOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="待审查" value={pendingCount} suffix="个" prefix={<EyeOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="修改中" value={regeneratingCount} suffix="个"
            valueStyle={{ color: '#3b82f6' }}
            prefix={regeneratingCount > 0 ? <LoadingOutlined /> : <CheckCircleOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Space>
              <Tag color="warning">⚠️ 待处理</Tag>
              <Text type="secondary">可编辑或让 AI 重新生成</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      {total === 0 ? (
        <Card>
          <Empty description={
            <Space direction="vertical" style={{ textAlign: 'center' }}>
              <Text type="secondary">暂无待审查的岗位</Text>
              <Text type="secondary">新建岗位并完成 AI 生成后，JD 会出现在这里</Text>
            </Space>
          } />
        </Card>
      ) : (
        <Collapse defaultActiveKey={departments} expandIconPosition="end" style={{ background: 'transparent' }}>
          {departments.map((dept: string) => {
            const jds = groups[dept] || [];
            return (
              <Panel key={dept}
                header={
                  <Space>
                    <TeamOutlined />
                    <Text strong style={{ fontSize: 16 }}>{dept}</Text>
                    <Tag>{jds.length} 个待处理</Tag>
                    {jds.some((j: any) => j.status === 'regenerating') && <Tag color="blue" icon={<LoadingOutlined />}>修改中</Tag>}
                  </Space>
                }
                style={{ marginBottom: 8, background: '#fff', borderRadius: 8 }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  {jds.map((jd: any) => {
                    const isRegenerating = jd.status === 'regenerating';
                    const isEditing = editing[jd.id];
                    const currentContent = isEditing ? editContent[jd.id] : jd.content;
                    const hasChanges = isEditing && currentContent !== jd.content;

                    return (
                      <Card
                        key={jd.id}
                        size="small"
                        style={{
                          borderLeft: `4px solid ${isRegenerating ? '#3b82f6' : '#faad14'}`,
                          marginBottom: 8,
                          opacity: isRegenerating ? 0.7 : 1,
                        }}
                        actions={[
                          <Tooltip title={isRegenerating ? '正在修改中...' : '审核通过 → 发布'}>
                            <Button type="primary" icon={<CheckCircleOutlined />}
                              loading={actionLoading === jd.id}
                              onClick={() => handleApprove(jd)} size="small" disabled={isRegenerating || isEditing}>
                              审核通过
                            </Button>
                          </Tooltip>,
                          <Tooltip title={isRegenerating ? '正在修改中...' : '驳回'}>
                            <Button danger icon={<CloseCircleOutlined />}
                              onClick={() => setRejectModal(jd)} size="small" disabled={isRegenerating || isEditing}>
                              驳回
                            </Button>
                          </Tooltip>,
                          <Tooltip title={isRegenerating ? '正在修改中...' : '让 AI 重新生成'}>
                            <Button icon={isRegenerating ? <LoadingOutlined /> : <ReloadOutlined />}
                              onClick={() => { setRegenerateModal(jd); setRegenerateHints(''); }}
                              size="small" disabled={isRegenerating || isEditing}>
                              重新生成
                            </Button>
                          </Tooltip>,
                          isEditing ? (
                            <Space key="edit-actions">
                              <Button icon={<SaveOutlined />} type="primary" size="small"
                                loading={saving[jd.id]} disabled={!hasChanges}
                                onClick={() => handleSave(jd.id)}>
                                保存
                              </Button>
                              <Button size="small" onClick={() => cancelEdit(jd.id)}>
                                取消
                              </Button>
                            </Space>
                          ) : (
                            <Tooltip title="直接编辑 JD 内容">
                              <Button icon={<EditOutlined />} size="small"
                                onClick={() => startEdit(jd)} disabled={isRegenerating}>
                                编辑
                              </Button>
                            </Tooltip>
                          ),
                        ].filter(Boolean)}
                      >
                        {isRegenerating && (
                          <Alert type="info" showIcon icon={<LoadingOutlined />}
                            message="🔄 AI 正在根据修改建议重新生成 JD，请稍候..."
                            style={{ marginBottom: 8, fontSize: 13 }} />
                        )}

                        <Space style={{ marginBottom: 8 }}>
                          <Text strong style={{ fontSize: 15 }}>{jd.title}</Text>
                          {isRegenerating ? (
                            <Tag color="blue" icon={<LoadingOutlined />}>🔄 修改中</Tag>
                          ) : isEditing ? (
                            <Tag color="orange" icon={<EditOutlined />}>编辑中</Tag>
                          ) : (
                            <Tag color="warning">⏳ 待审查</Tag>
                          )}
                          <Tag color={jd.urgency === 'urgent' ? 'red' : jd.urgency === 'high' ? 'orange' : 'blue'}>
                            {jd.urgency === 'urgent' ? '紧急' : jd.urgency === 'high' ? '重要' : '普通'}
                          </Tag>
                          {jd.headcount > 1 && <Tag color="purple">×{jd.headcount}人</Tag>}
                        </Space>

                        <div style={{ marginBottom: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {jd.budget_range && `💰 ${jd.budget_range} | `}
                            创建于 {jd.created_at ? new Date(jd.created_at).toLocaleString('zh-CN') : '未知'}
                            {jd.review_comment && (
                              <span style={{ marginLeft: 8, color: '#f59e0b' }}>
                                | 💡 修改建议: {jd.review_comment.slice(0, 60)}...
                              </span>
                            )}
                          </Text>
                        </div>

                        <Divider style={{ margin: '6px 0' }} />

                        {!isRegenerating && jd.raw_requirements && !isEditing && (
                          <div style={{ marginBottom: 6 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>📝 原始需求：</Text>
                            <Paragraph ellipsis={{ rows: 1, expandable: true, symbol: '展开' }}
                              style={{ fontSize: 13, margin: 0, color: '#666' }}>
                              {jd.raw_requirements}
                            </Paragraph>
                          </div>
                        )}

                        {/* JD 内容：编辑模式用 TextArea，查看模式用 pre */}
                        {isEditing ? (
                          <TextArea rows={12}
                            value={editContent[jd.id] || ''}
                            onChange={(e) => setEditContent(prev => ({ ...prev, [jd.id]: e.target.value }))}
                            style={{ fontFamily: 'monospace', fontSize: 13 }}
                          />
                        ) : (
                          <div style={{
                            background: '#f8fafc', padding: 12, borderRadius: 8,
                            border: '1px solid #e2e8f0',
                            maxHeight: 200, overflow: 'auto',
                            whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12,
                          }}>
                            {isRegenerating ? '（AI 正在重新生成中...）' : (jd.content || jd.original_content || '暂无内容')}
                          </div>
                        )}
                      </Card>
                    );
                  })}
                </Space>
              </Panel>
            );
          })}
        </Collapse>
      )}

      {/* 驳回弹窗 */}
      <Modal title="❌ 驳回岗位" open={!!rejectModal}
        onOk={handleReject} onCancel={() => { setRejectModal(null); setRejectReason(''); }}
        confirmLoading={actionLoading !== null} okText="确认驳回" cancelText="取消" okButtonProps={{ danger: true }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>确定驳回 <Text strong>{rejectModal?.title}</Text> 吗？</Text>
          <TextArea rows={3} placeholder="填写驳回原因（可选）"
            value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
        </Space>
      </Modal>

      {/* 重新生成弹窗 */}
      <Modal title={<Space><ReloadOutlined style={{ color: '#3b82f6' }} /> AI 重新生成 JD</Space>}
        open={!!regenerateModal} onOk={handleRegenerate}
        onCancel={() => { setRegenerateModal(null); setRegenerateHints(''); }}
        confirmLoading={actionLoading !== null} okText="确认重新生成" cancelText="取消" width={600}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>希望对 <Text strong>{regenerateModal?.title}</Text> 进行修改：</Text>
          <div style={{
            background: '#f8fafc', padding: 12, borderRadius: 8,
            border: '1px solid #e2e8f0', maxHeight: 150, overflow: 'auto',
            whiteSpace: 'pre-wrap', fontSize: 12, marginTop: 8,
          }}>
            {regenerateModal?.content || '（暂无内容）'}
          </div>
          <TextArea rows={5}
            placeholder={`例如：\n1. 把经验要求从3年改为5年\n2. 增加 Go 语言作为加分项\n3. 把薪资调整为 40K-60K`}
            value={regenerateHints} onChange={(e) => setRegenerateHints(e.target.value)} />
          <Alert type="info" showIcon message="修改建议是硬性要求，AI 会严格按你的指示修改。" style={{ fontSize: 12 }} />
        </Space>
      </Modal>
    </div>
  );
};

export default JDReviewPage;
