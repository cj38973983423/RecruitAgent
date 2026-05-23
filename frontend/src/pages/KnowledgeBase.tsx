import React, { useEffect, useState } from 'react';
import {
  Card, Typography, Button, Upload, Table, Tag, Space,
  Modal, Input, message, Statistic, Row, Col, Empty, Alert, Popconfirm,
} from 'antd';
import {
  UploadOutlined, InboxOutlined, DatabaseOutlined, SearchOutlined,
  FileTextOutlined, DeleteOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;

const API = '/api/knowledge-base';

const KnowledgeBase: React.FC = () => {
  const [status, setStatus] = useState<any>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchModal, setSearchModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [addTextModal, setAddTextModal] = useState(false);
  const [addForm, setAddForm] = useState({ title: '', content: '', skills: '', industry: '' });

  // 批量删除状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);

  const loadStatus = async () => {
    try {
      const res = await axios.get(`${API}/status`);
      setStatus(res.data);
    } catch { /* ignore */ }
  };

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/documents`);
      setDocuments(res.data.documents || []);
    } catch {
      message.error('加载知识库失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    loadDocuments();
  }, []);

  const handleUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post(`${API}/upload`, fd);
      message.success(`✅ ${res.data.message}`);
      onSuccess?.({});
      loadDocuments();
      loadStatus();
    } catch (err: any) {
      onError?.(err);
      message.error(`上传失败: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await axios.post(`${API}/search`, { query: searchQuery, top_k: 10 });
      setSearchResults(res.data.results || []);
    } catch {
      message.error('搜索失败');
    }
  };

  const handleAddText = async () => {
    if (!addForm.title || !addForm.content) {
      message.warning('请填写标题和内容');
      return;
    }
    try {
      await axios.post(`${API}/add-text`, addForm);
      message.success(`「${addForm.title}」已加入知识库`);
      setAddTextModal(false);
      setAddForm({ title: '', content: '', skills: '', industry: '' });
      loadDocuments();
      loadStatus();
    } catch {
      message.error('添加失败');
    }
  };

  const handleDelete = async (docId: number) => {
    try {
      await axios.delete(`${API}/documents/${docId}`);
      message.success('已删除');
      loadDocuments();
      loadStatus();
    } catch {
      message.error('删除失败');
    }
  };

  /** 批量删除 */
  const handleBatchDelete = () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: `确认删除选中的 ${selectedRowKeys.length} 个文档？`,
      icon: <ExclamationCircleOutlined />,
      content: '删除后不可恢复，知识库需要重新导入这些文档。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setBatchDeleting(true);
        try {
          const res = await axios.post(`${API}/documents/batch-delete`, {
            doc_ids: selectedRowKeys,
          });
          message.success(res.data.message);
          setSelectedRowKeys([]);
          loadDocuments();
          loadStatus();
        } catch (err: any) {
          message.error('批量删除失败: ' + (err?.response?.data?.detail || err.message));
        } finally {
          setBatchDeleting(false);
        }
      },
    });
  };

  const handleSeed = async () => {
    try {
      const res = await axios.post(`${API}/seed-standard`);
      message.success(res.data.message);
      loadDocuments();
      loadStatus();
    } catch {
      message.error('预置失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '行业', dataIndex: 'industry', key: 'industry', render: (v: string) => v || '-', width: 120 },
    {
      title: '来源', dataIndex: 'source', key: 'source',
      render: (v: string) => {
        const colors: Record<string, string> = { upload: 'blue', manual: 'green', standard: 'purple' };
        return <Tag color={colors[v] || 'default'}>{v}</Tag>;
      }, width: 90,
    },
    {
      title: '技能标签', dataIndex: 'skills', key: 'skills', render: (s: string) => {
        if (!s) return '-';
        return s.split(',').filter(Boolean).map((sk: string) => (
          <Tag key={sk} color="blue" style={{ fontSize: 11, marginBottom: 2 }}>{sk.trim()}</Tag>
        ));
      },
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: any, record: any) => (
        <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
          <Button type="link" size="small" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>
        <DatabaseOutlined style={{ marginRight: 8, color: '#3b82f6' }} />
        📚 JD 知识库 (RAG)
      </Title>
      <Paragraph type="secondary">
        AI 在进行 JD 增强时，会检索知识库中的相似标准 JD 作为参考。
        支持上传 PDF / DOCX / TXT 文档，或手动添加文本。
      </Paragraph>

      {/* 状态 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="文档总数"
              value={status?.total_documents ?? documents.length}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="存储引擎" value={status?.backend === 'milvus_lite' ? 'Milvus Lite' : '本地存储'} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="状态" value={status?.status === 'connected' ? '✅ 正常' : '⚠️ 异常'}
              valueStyle={{ color: status?.status === 'connected' ? '#22c55e' : '#ef4444' }} />
          </Card>
        </Col>
      </Row>

      {/* 操作栏 */}
      <Card style={{ marginBottom: 16 }} size="small">
        <Space wrap>
          <Button icon={<SearchOutlined />} onClick={() => setSearchModal(true)}>
            搜索知识库
          </Button>
          <Button icon={<FileTextOutlined />} onClick={() => setAddTextModal(true)}>
            手动添加
          </Button>
          <Button onClick={handleSeed}>
            🌱 预置标准 JD
          </Button>
          <Button onClick={() => { loadDocuments(); loadStatus(); }}>
            🔄 刷新
          </Button>
          {/* 批量删除 */}
          {selectedRowKeys.length > 0 && (
            <Button
              danger
              type="primary"
              icon={<DeleteOutlined />}
              loading={batchDeleting}
              onClick={handleBatchDelete}
            >
              批量删除 ({selectedRowKeys.length})
            </Button>
          )}
        </Space>
      </Card>

      {/* 上传区域 */}
      <Card style={{ marginBottom: 16 }}>
        <Dragger
          customRequest={handleUpload}
          multiple
          showUploadList={false}
          accept=".pdf,.docx,.doc,.txt"
        >
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">拖拽 JD 文档到此处，或点击选择文件</p>
          <p className="ant-upload-hint">支持 PDF / DOCX / TXT 格式，上传后自动提取文本并向量化</p>
        </Dragger>
      </Card>

      {/* 文档列表 */}
      <Card title={`知识库文档（${documents.length}）`}>
        <Table
          dataSource={documents}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          locale={{ emptyText: <Empty description="知识库为空，上传一些 JD 文档吧" /> }}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          // 批量选择
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
          }}
        />
      </Card>

      {/* 搜索弹窗 */}
      <Modal
        title="🔍 搜索知识库"
        open={searchModal}
        onCancel={() => { setSearchModal(false); setSearchResults([]); }}
        footer={null}
        width={700}
      >
        <Space style={{ width: '100%', marginBottom: 16 }}>
          <Input.Search
            placeholder="输入搜索关键词，如「高级 Python 后端」"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onSearch={handleSearch}
            enterButton="搜索"
            style={{ flex: 1 }}
          />
        </Space>
        {searchResults.length > 0 && (
          <div>
            <Text type="secondary">找到 {searchResults.length} 条结果</Text>
            {searchResults.map((r: any, i: number) => (
              <Card key={i} size="small" style={{ marginTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text strong>{r.job_title || '未知'}</Text>
                  <Tag color={r.score > 0.7 ? 'green' : r.score > 0.4 ? 'orange' : 'default'}>
                    {(r.score * 100).toFixed(0)}% 匹配
                  </Tag>
                </div>
                <Paragraph style={{ fontSize: 12, margin: 0 }} ellipsis={{ rows: 3 }}>
                  {r.content}
                </Paragraph>
                {r.skills && (
                  <div style={{ marginTop: 4 }}>
                    {r.skills.split(',').filter(Boolean).map((s: string) => (
                      <Tag key={s} color="blue" style={{ fontSize: 10 }}>{s.trim()}</Tag>
                    ))}
                  </div>
                )}
                {r.industry && <Tag color="purple" style={{ fontSize: 10 }}>{r.industry}</Tag>}
              </Card>
            ))}
          </div>
        )}
      </Modal>

      {/* 手动添加弹窗 */}
      <Modal
        title="✍️ 手动添加文档"
        open={addTextModal}
        onCancel={() => setAddTextModal(false)}
        onOk={handleAddText}
        okText="添加"
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input placeholder="文档标题（如：高级 Python 后端工程师 JD）"
            value={addForm.title}
            onChange={(e) => setAddForm({ ...addForm, title: e.target.value })} />
          <Input placeholder="行业（如：互联网/科技）"
            value={addForm.industry}
            onChange={(e) => setAddForm({ ...addForm, industry: e.target.value })} />
          <Input placeholder="技能标签，逗号分隔（如：Python,FastAPI,SQL）"
            value={addForm.skills}
            onChange={(e) => setAddForm({ ...addForm, skills: e.target.value })} />
          <TextArea rows={8} placeholder="粘贴 JD 全文..."
            value={addForm.content}
            onChange={(e) => setAddForm({ ...addForm, content: e.target.value })} />
        </Space>
      </Modal>
    </div>
  );
};

export default KnowledgeBase;
