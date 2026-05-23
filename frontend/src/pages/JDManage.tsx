import React, { useEffect, useState } from 'react';
import {
  Card, Typography, Button, Tag, Space, Spin, message,
  Collapse, Descriptions, Divider, Empty, Row, Col, Statistic, Tooltip, Modal,
} from 'antd';
import {
  CheckCircleOutlined, ApartmentOutlined, TeamOutlined,
  FileTextOutlined, UserOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { listApprovedJDs, deleteJD } from '../api';
import { useNavigate } from 'react-router-dom';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

const JDManage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const result = await listApprovedJDs();
      setData(result);
    } catch (err) {
      message.error('加载岗位列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (jd: any) => {
    Modal.confirm({
      title: `确认删除岗位「${jd.position_name || jd.title}」？`,
      content: '删除后将不可恢复，关联的简历筛选工作流也将移除。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteJD(jd.id);
          message.success(`已删除「${jd.title}」`);
          loadData();
        } catch (err: any) {
          message.error('删除失败: ' + (err?.response?.data?.detail || err.message));
        }
      },
    });
  };

  useEffect(() => { loadData(); }, []);

  if (loading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;

  const groups = data?.groups || {};
  const departments = data?.departments || [];
  const total = data?.total || 0;

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="已通过岗位" value={total} suffix="个" valueStyle={{ color: '#22c55e' }} prefix={<CheckCircleOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="涉及部门" value={departments.length} suffix="个" prefix={<ApartmentOutlined />} /></Card>
        </Col>
        <Col span={12}>
          <Card>
            <Space>
              <Tag color="success">✅ 已通过</Tag>
              <Text type="secondary">人工审查通过的岗位，已发布并可启动简历筛选</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      {total === 0 ? (
        <Card>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical" style={{ textAlign: 'center' }}>
                <Text type="secondary">暂无已通过的岗位</Text>
                <Text type="secondary">请先在「新建岗位」创建需求，AI生成JD后到「岗位人工审查」审核通过</Text>
                <Button type="primary" onClick={() => navigate('/new')}>➕ 新建岗位</Button>
              </Space>
            }
          />
        </Card>
      ) : (
        <Collapse
          defaultActiveKey={departments}
          expandIconPosition="end"
          style={{ background: 'transparent' }}
        >
          {departments.map((dept: string) => {
            const jds = groups[dept] || [];
            return (
              <Panel
                key={dept}
                header={
                  <Space>
                    <TeamOutlined />
                    <Text strong style={{ fontSize: 16 }}>{dept}</Text>
                    <Tag color="green">{jds.length} 个岗位</Tag>
                    {jds.some((j: any) => j.is_filled) && (
                      <Tag color="red" style={{ fontWeight: 600 }}>🈵 含已招满岗位</Tag>
                    )}
                  </Space>
                }
                style={{ marginBottom: 8, background: '#fff', borderRadius: 8 }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  {jds.map((jd: any) => (
                    <Card
                      key={jd.id}
                      size="small"
                      style={{
                        borderLeft: jd.is_filled ? '4px solid #f5222d' : '4px solid #22c55e',
                        marginBottom: 8,
                        background: jd.is_filled ? '#fff1f0' : '#fff',
                        opacity: jd.is_filled ? 0.92 : 1,
                      }}
                      actions={[
                        <Tooltip title={jd.is_filled ? "该岗位已招满，简历将进入候选池留存" : "前往简历管理，上传候选人简历"}>
                          <Button
                            type="primary"
                            ghost={!jd.is_filled}
                            icon={<UserOutlined />}
                            onClick={() => navigate('/resumes')}
                            size="small"
                            style={jd.is_filled ? { color: '#999', borderColor: '#d9d9d9' } : {}}
                          >
                            {jd.is_filled ? '查看简历' : '管理简历'}
                          </Button>
                        </Tooltip>,
                        <Tooltip title="查看该岗位的招聘流程详情">
                          <Button
                            icon={<FileTextOutlined />}
                            onClick={() => navigate(`/workflow/${jd.request_id}`)}
                            size="small"
                          >
                            查看流程
                          </Button>
                        </Tooltip>,
                        <Tooltip title="删除此岗位">
                          <Button
                            danger
                            type="link"
                            icon={<DeleteOutlined />}
                            onClick={() => handleDelete(jd)}
                            size="small"
                          >
                            删除
                          </Button>
                        </Tooltip>,
                      ]}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ flex: 1 }}>
                          <Space>
                            <Text strong style={{ fontSize: 15 }}>{jd.position_name || jd.title}</Text>
                            <Tag color={jd.urgency === 'urgent' ? 'red' : jd.urgency === 'high' ? 'orange' : 'blue'}>
                              {jd.urgency === 'urgent' ? '紧急' : jd.urgency === 'high' ? '重要' : '普通'}
                            </Tag>
                            {jd.headcount > 1 && <Tag color="purple">×{jd.headcount}人</Tag>}
                            {jd.is_filled && (
                              <Tag
                                color="red"
                                style={{
                                  fontSize: 13, fontWeight: 700, padding: '2px 10px',
                                  border: '2px solid #f5222d', borderRadius: 4,
                                }}
                              >
                                🚫 已招满
                              </Tag>
                            )}
                            {!jd.is_filled && jd.filled_count > 0 && jd.headcount > 1 && (
                              <Tag color="orange" style={{ fontSize: 12, fontWeight: 600 }}>🔥 {jd.filled_count}/{jd.headcount} 已招</Tag>
                            )}
                            {jd.vector_synced && <Tag color="geekblue">已同步知识库</Tag>}
                          </Space>

                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              创建于 {jd.created_at ? new Date(jd.created_at).toLocaleString('zh-CN') : '未知'}
                            </Text>
                          </div>

                          <Divider style={{ margin: '8px 0' }} />

                          {/* 已招满横幅 */}
                          {jd.is_filled && (
                            <div style={{
                              background: 'linear-gradient(90deg, #fff1f0, #ffccc7)',
                              border: '1px solid #ff4d4f', borderRadius: 6, padding: '6px 12px',
                              marginBottom: 8, textAlign: 'center',
                            }}>
                              <Text style={{ color: '#cf1322', fontWeight: 700, fontSize: 13 }}>
                                🚫 该岗位已招满，不可再发 Offer
                              </Text>
                            </div>
                          )}

                          {/* JD 内容预览 */}
                          <div style={{
                            background: '#f0fdf4', padding: 12, borderRadius: 8,
                            border: '1px solid #bbf7d0',
                            maxHeight: 150, overflow: 'auto',
                            whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12,
                          }}>
                            {jd.content || '暂无 JD 内容'}
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </Space>
              </Panel>
            );
          })}
        </Collapse>
      )}
    </div>
  );
};

export default JDManage;
