import React, { useEffect, useState, useRef } from 'react';
import {
  Card, Typography, Button, Table, Tag, Space, Upload,
  Modal, Input, message, Descriptions, Alert, Tabs, Badge, Popconfirm, Select, Tooltip,
} from 'antd';
import { UploadOutlined, InboxOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { listResumes, uploadResume, batchAction, deleteResume, listApprovedJDs, updateResumeNotes, updateResumeJD } from '../api';
import { EmptyGuide, stepIcons } from '../components/EmptyGuide';
import type { Resume, JobDescription } from '../types';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;

const ResumeManage: React.FC = () => {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [detailModal, setDetailModal] = useState<Resume | null>(null);
  const [tabKey, setTabKey] = useState('all');
  const [jdList, setJdList] = useState<JobDescription[]>([]);
  const [selectedJdId, setSelectedJdId] = useState<number | undefined>(undefined);
  const [filterJdId, setFilterJdId] = useState<number | undefined>(undefined);
  const [notesText, setNotesText] = useState('');
  const [editingJDResumeId, setEditingJDResumeId] = useState<number | null>(null);

  const loadResumes = async (status?: string, jdFilter?: number) => {
    setLoading(true);
    try {
      const params: any = { page: 1, pageSize: 100 };
      if (status && status !== 'all') params.status = status;
      if (jdFilter) params.jd_id = jdFilter;
      const data = await listResumes(params);
      setResumes(data.items || []);
    } catch {
      message.error('加载简历列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const statusMap: Record<string, string | undefined> = {
      all: undefined,
      ai_pass: 'ai_pass',
      ai_reject: 'ai_reject',
      manual_pass: 'manual_pass',
    };
    loadResumes(statusMap[tabKey], filterJdId);
    // 加载已审批的岗位列表
    listApprovedJDs().then((data: any) => {
      const options: any[] = [];
      const groups = data?.groups || {};
      Object.entries(groups).forEach(([dept, jds]: any) => {
        (jds as any[]).forEach((jd: any) => {
          options.push({ id: jd.id, label: `${jd.title || jd.position_name}（${dept}）` });
        });
      });
      setJdList(options);
    }).catch(() => {});
  }, [tabKey]);

  const handleUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    try {
      const res = await uploadResume(file as File, selectedJdId);
      const jdName = selectedJdId ? jdList.find(j => j.id === selectedJdId)?.label || '' : '';
      message.success(`✅ 上传成功: ${(file as any).name}${jdName ? `（${jdName}）` : ''}，AI 分析中...`);
      setSelectedJdId(undefined);
      onSuccess?.({});
      loadResumes();
      // 延迟刷新以获取后台分析结果
      setTimeout(() => loadResumes(), 5000);
    } catch (err: any) {
      onError?.(err);
      message.error(`上传失败: ${(file as any).name}`);
    }
  }; // end handleUpload

  const handleDeleteResume = (resume: any) => {
    Modal.confirm({
      title: `确认删除简历「${resume.name || resume.file_name || '未知'}」？`,
      content: '删除后将不可恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteResume(resume.id);
          message.success('已删除');
          loadResumes();
        } catch (err: any) {
          message.error('删除失败: ' + (err?.response?.data?.detail || err.message));
        }
      },
    });
  };

  const handleManualPass = async (resume: any) => {
    try {
      await batchAction({ resume_ids: [resume.id], action: 'pass' });
      message.success(`✅ 已标记「${resume.name || resume.file_name}」为人工通过`);
      loadResumes();
    } catch (err: any) {
      message.error('操作失败: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleSaveNotes = async () => {
    if (!detailModal) return;
    try {
      await updateResumeNotes(detailModal.id, notesText);
      message.success('📝 备注已保存');
      setDetailModal({ ...detailModal, notes: notesText });
    } catch (err: any) {
      message.error('保存失败: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleChangeJD = async (resumeId: number, jdId: number | undefined) => {
    try {
      const updated = await updateResumeJD(resumeId, jdId ?? null);
      setResumes(prev => prev.map(r => r.id === resumeId ? { ...r, ...updated } : r));
      message.success(`✅ 已${jdId ? '关联' : '取消关联'}岗位`);
    } catch (err: any) {
      message.error('操作失败: ' + (err?.response?.data?.detail || err.message));
    }
    setEditingJDResumeId(null);
  };

  const openDetailModal = (record: any) => {
    setNotesText(record.notes || '');
    setDetailModal(record);
  };

  const handleBatchAction = async (action: string) => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择简历');
      return;
    }
    try {
      await batchAction({ resume_ids: selectedRowKeys, action });
      message.success(`批量${action === 'pass' ? '通过' : '淘汰'}完成`);
      setSelectedRowKeys([]);
      loadResumes();
    } catch {
      message.error('操作失败');
    }
  };

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name', render: (n: string) => n || '（未解析）' },
    {
      title: '匹配岗位', key: 'jd', width: 200,
      render: (_: any, record: any) => {
        if (editingJDResumeId === record.id) {
          return (
            <Select
              autoFocus
              showSearch
              size="small"
              style={{ width: 180 }}
              placeholder="选择岗位"
              allowClear
              defaultOpen
              optionFilterProp="label"
              value={record.jd_id}
              onChange={(val) => handleChangeJD(record.id, val)}
              onBlur={() => setEditingJDResumeId(null)}
              options={jdList.map(j => ({ value: j.id, label: j.label }))}
            />
          );
        }
        const label = record.jd_title
          || (record.jd_id && jdList.find(j => j.id === record.jd_id)?.label)
          || null;
        return (
          <div
            style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}
            onClick={() => setEditingJDResumeId(record.id)}
            title="点击切换岗位"
          >
            {label
              ? <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>{label}</Tag>
              : <Tag style={{ fontSize: 11, margin: 0, cursor: 'pointer' }} color="default">未关联</Tag>
            }
            <EditOutlined style={{ fontSize: 11, color: '#999', opacity: 0.6 }} />
          </div>
        );
      },
    },
    {
      title: '技能', dataIndex: 'skills', key: 'skills', width: 250,
      render: (s: string) => {
        if (!s) return '-';
        try {
          const skills = JSON.parse(s);
          return (skills as string[]).map((sk: string) => (
            <Tag key={sk} color="blue" style={{ fontSize: 11, marginBottom: 2 }}>{sk}</Tag>
          ));
        } catch {
          return <Tag>{s}</Tag>;
        }
      },
    },
    { title: '经验', dataIndex: 'experience_years', key: 'exp', width: 80,
      render: (v: number) => v ? `${v} 年` : '-' },
    {
      title: 'AI 评分', dataIndex: 'ai_score', key: 'score', width: 100,
      sorter: (a: any, b: any) => (a.ai_score || 0) - (b.ai_score || 0),
      render: (score: number) => {
        if (score === null || score === undefined) return '-';
        const color = score >= 80 ? 'green' : score >= 60 ? 'orange' : 'red';
        return <Tag color={color}>{score}</Tag>;
      },
    },
    {
      title: 'AI 推荐', dataIndex: 'ai_recommended', key: 'recommended', width: 90,
      render: (v: boolean) => v ? <Tag color="green">推荐</Tag> : '-',
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        const cfg: Record<string, { color: string; label: string }> = {
          pending:     { color: 'default', label: '待处理' },
          ai_pass:     { color: 'blue',    label: 'AI 通过' },
          ai_reject:   { color: 'red',     label: 'AI 淘汰' },
          manual_pass: { color: 'green',   label: '人工通过' },
          manual_reject: { color: 'volcano', label: '人工淘汰' },
        };
        const c = cfg[s] || { color: 'default', label: s };
        return <Tag color={c.color}>{c.label}</Tag>;
      },
    },
    {
      title: '备注', key: 'notes', width: 180,
      render: (_: any, record: any) => {
        const notes = record.notes || '';
        return notes ? (
          <Tooltip title={notes}>
            <Text
              ellipsis={{ tooltip: notes }}
              style={{ maxWidth: 160, display: 'inline-block', cursor: 'pointer' }}
              onClick={() => openDetailModal(record)}
            >
              {notes}
            </Text>
          </Tooltip>
        ) : (
          <Text type="secondary" style={{ cursor: 'pointer' }} onClick={() => openDetailModal(record)}>
            添加备注+
          </Text>
        );
      },
    },
    {
      title: '操作', key: 'action', width: 280,
      render: (_: any, record: any) => (
        <Space size="small" wrap>
          <Button type="link" size="small" onClick={() => openDetailModal(record)}>详情</Button>
          {(record.status === 'ai_pass' || record.status === 'ai_reject') && (
            <Popconfirm
              title={`确认人工通过「${record.name || record.file_name || '未知'}」？`}
              description="通过后该简历将进入面试候选池"
              onConfirm={() => handleManualPass(record)}
              okText="通过" cancelText="取消"
            >
              <Button type="link" size="small" style={{ color: '#52c41a' }}>✅ 人工通过</Button>
            </Popconfirm>
          )}
          <Button type="link" size="small" danger icon={<DeleteOutlined />}
            onClick={() => handleDeleteResume(record)}>删除</Button>
        </Space>
      ),
    },
  ];

  const tabItems = [
    { key: 'all', label: `📄 全部 (${resumes.length})` },
    { key: 'ai_pass', label: '🤖 AI 通过' },
    { key: 'ai_reject', label: '🤖 AI 淘汰' },
    { key: 'manual_pass', label: '👤 人工通过' },
  ];

  return (
    <div>
      <Title level={3}>📄 简历管理</Title>

      {/* 上传区域 */}
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text strong style={{ whiteSpace: 'nowrap' }}>选择岗位：</Text>
            <Select
              placeholder="选择对应岗位进行 AI 匹配评估"
              value={selectedJdId}
              onChange={setSelectedJdId}
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ minWidth: 320 }}
              notFoundContent="暂无已审批的岗位，请先在岗位管理创建并审批"
              options={jdList.map(j => ({ value: j.id, label: j.label }))}
            />
          </div>
          <Dragger customRequest={handleUpload} multiple showUploadList={false}
            accept=".pdf,.docx,.doc">
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">拖拽 PDF / DOCX 到此处，或点击选择文件</p>
            <p className="ant-upload-hint">
              {selectedJdId
                ? `将基于所选岗位进行 AI 技能匹配和评分`
                : '未选择岗位时将仅做解析，不会进行 AI 匹配评分'}
            </p>
          </Dragger>
        </Space>
      </Card>

      {/* 批量操作 */}
      <Card style={{ marginBottom: 16 }} size="small">
        <Space>
          <Text>已选 {selectedRowKeys.length} 份简历</Text>
          <Button type="primary" onClick={() => handleBatchAction('pass')}>
            ✅ 批量通过
          </Button>
          <Button danger onClick={() => handleBatchAction('reject')}>
            ❌ 批量淘汰
          </Button>
          <span style={{ width: 1, height: 24, background: '#d9d9d9', margin: '0 8px', display: 'inline-block' }} />
          <Text type="secondary" style={{ fontSize: 13 }}>按匹配岗位筛选：</Text>
          <Select
            placeholder="全部岗位"
            value={filterJdId}
            onChange={(val) => { setFilterJdId(val); }}
            allowClear
            showSearch
            optionFilterProp="label"
            style={{ minWidth: 200 }}
            onClear={() => setFilterJdId(undefined)}
            options={jdList.map(j => ({ value: j.id, label: j.label }))}
          />
        </Space>
      </Card>

      {/* 简历列表 */}
      <Card>
        <Tabs activeKey={tabKey} onChange={setTabKey} items={tabItems} />
        <Table
          dataSource={resumes}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          locale={{
            emptyText: resumes.length === 0 && !loading ? (
              <EmptyGuide
                title="还没有简历数据"
                description="按照以下步骤开始招聘流程"
                steps={[
                  { icon: stepIcons.jd, label: '创建岗位需求' },
                  { icon: stepIcons.review, label: '审批通过岗位' },
                  { icon: stepIcons.upload, label: '上传简历(PDF/DOCX)' },
                ]}
              />
            ) : '暂无数据',
          }}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
          }}
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      </Card>

      {/* 详情弹窗 */}
      <Modal
        title={`简历详情 - ${detailModal?.name || '未知'}`}
        open={!!detailModal}
        onCancel={() => setDetailModal(null)}
        footer={null}
        width={720}
      >
        {detailModal && (
          <div>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="姓名">{detailModal.name || '-'}</Descriptions.Item>
              <Descriptions.Item label="经验年限">{detailModal.experience_years || '-'} 年</Descriptions.Item>
              <Descriptions.Item label="AI 评分">
                <Tag color={detailModal.ai_score >= 80 ? 'green' : detailModal.ai_score >= 60 ? 'orange' : 'red'}>
                  {detailModal.ai_score ?? '-'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag>{detailModal.status}</Tag>
              </Descriptions.Item>
            </Descriptions>

            {detailModal.deep_analysis && (
              <div style={{ marginTop: 16 }}>
                <Title level={5}>🔍 深度分析</Title>
                <AnalysisResult data={detailModal.deep_analysis} />
              </div>
            )}

            {detailModal.ai_reason && (
              <Alert
                message="AI 推荐理由"
                description={detailModal.ai_reason}
                type="info"
                showIcon
                style={{ marginTop: 12 }}
              />
            )}

            {/* 内部备注 */}
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Title level={5} style={{ margin: 0 }}>📝 内部备注</Title>
                <Button size="small" type="primary" onClick={handleSaveNotes}>保存备注</Button>
              </div>
              <TextArea
                rows={3}
                placeholder="添加内部备注，仅HR可见，如：已电话沟通、候选人待跟进..."
                value={notesText}
                onChange={e => setNotesText(e.target.value)}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

const AnalysisResult: React.FC<{ data: any }> = ({ data }) => {
  return (
    <div>
      {data.project_authenticity && (
        <Card title="🏗️ 项目真实性" size="small" style={{ marginBottom: 8 }}>
          <Tag color={data.project_authenticity.score >= 70 ? 'green' : 'orange'}>
            评分: {data.project_authenticity.score}
          </Tag>
          {data.project_authenticity.details && (
            <Paragraph style={{ marginTop: 8, fontSize: 12 }}>{data.project_authenticity.details}</Paragraph>
          )}
          {data.project_authenticity.flags?.length > 0 && (
            <Alert message="可疑信号" description={data.project_authenticity.flags.join('; ')} type="warning" showIcon />
          )}
        </Card>
      )}
      {data.risk_warnings && data.risk_warnings.length > 0 && (
        <Card title="⚠️ 风险预警" size="small" style={{ marginBottom: 8, border: '1px solid #ffa39e' }}>
          {data.risk_warnings.map((w: any, i: number) => (
            <Alert
              key={i}
              message={`[${w.severity}] ${w.type}`}
              description={w.detail}
              type={w.severity === 'high' ? 'error' : w.severity === 'medium' ? 'warning' : 'info'}
              showIcon
              style={{ marginBottom: 4 }}
            />
          ))}
        </Card>
      )}
      {data.frequent_job_change && (
        <Alert message="⚠️ 频繁跳槽风险" type="warning" showIcon style={{ marginBottom: 8 }} />
      )}
      {data.career_trajectory && (
        <Card title="📈 职业晋升轨迹" size="small" style={{ marginBottom: 8 }}>
          <Tag color={data.career_trajectory.trend === '上升' ? 'green' : 'default'}>
            {data.career_trajectory.trend}
          </Tag>
          <Paragraph style={{ marginTop: 8, fontSize: 12 }}>{data.career_trajectory.analysis}</Paragraph>
        </Card>
      )}
    </div>
  );
};

export default ResumeManage;
