import React, { useState, useRef, useEffect } from 'react';
import {
  Card, Form, Input, Select, InputNumber, Button, Typography,
  message, Steps, Space, Spin, Progress, Empty,
} from 'antd';
import {
  RocketOutlined, CheckCircleOutlined,
  RobotOutlined, CloseCircleOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import { startWorkflow } from '../api';
import { useNavigate } from 'react-router-dom';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

const AI_TIMEOUT = 180_000;

/** 单页面岗位创建流程（简化版：无多轮澄清，直接 AI 增强 → 生成 JD） */
const NewRequest: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const [step, setStep] = useState<'form' | 'running' | 'completed' | 'error'>('form');
  const [loading, setLoading] = useState(false);
  const [requestId, setRequestId] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [jdText, setJdText] = useState('');

  const loadingTimerRef = useRef<number | null>(null);

  const setLoadingWithTimeout = () => {
    setLoading(true);
    if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
    loadingTimerRef.current = window.setTimeout(() => {
      setLoading(false);
      message.warning('⏱️ 请求时间过长，AI 生成可能需要较长时间，请检查后端是否正常');
    }, AI_TIMEOUT);
  };

  const clearLoading = () => {
    setLoading(false);
    if (loadingTimerRef.current) {
      clearTimeout(loadingTimerRef.current);
      loadingTimerRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
    };
  }, []);

  const handleSubmit = async (values: any) => {
    setErrorMsg('');
    setLoadingWithTimeout();
    setStep('running');
    setRequestId(null);

    try {
      const result = await startWorkflow(values);
      setRequestId(result.request_id);

      if (result.jd_id && result.enhanced_jd_text) {
        setJdText(result.enhanced_jd_text);
        setStep('completed');
        message.success('✅ JD 已由 AI 增强生成，请前往审查！');
      } else {
        setStep('error');
        setErrorMsg('工作流返回异常，未生成 JD');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message || '未知错误';
      message.error('生成失败: ' + detail);
      setErrorMsg(detail);
      setStep('error');
    } finally {
      clearLoading();
    }
  };

  const handleReset = () => {
    setStep('form');
    setRequestId(null);
    setJdText('');
    setErrorMsg('');
    form.resetFields();
    clearLoading();
  };

  const renderForm = () => (
    <Card>
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap>
            <Form.Item name="department" label="需求部门" rules={[{ required: true, message: '请输入部门' }]} style={{ marginBottom: 0 }}>
              <Input placeholder="如：技术部" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="position_name" label="职位名称" rules={[{ required: true, message: '请输入职位名称' }]} style={{ marginBottom: 0 }}>
              <Input placeholder="如：高级 Python 后端工程师" style={{ width: 280 }} />
            </Form.Item>
          </Space>
          <Space wrap>
            <Form.Item name="headcount" label="招聘人数" initialValue={1} style={{ marginBottom: 0 }}>
              <InputNumber min={1} max={100} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="urgency" label="紧急程度" initialValue="normal" style={{ marginBottom: 0 }}>
              <Select style={{ width: 140 }}
                options={[
                  { value: 'urgent', label: '🔥 紧急' },
                  { value: 'high', label: '⚡ 高' },
                  { value: 'normal', label: '📌 普通' },
                  { value: 'low', label: '⏳ 低' },
                ]}
              />
            </Form.Item>
            <Form.Item name="budget_range" label="薪资预算" style={{ marginBottom: 0 }}>
              <Input placeholder="如：30K-50K" style={{ width: 160 }} />
            </Form.Item>
          </Space>
          <Form.Item name="raw_requirements" label="招聘需求描述"
            extra="即使需求模糊也不怕，AI 会基于你的描述自动补充完善。描述越详细效果越好！"
            rules={[{ required: true, message: '请描述招聘需求' }]}
          >
            <TextArea rows={5} placeholder={`请描述招聘需求，例如岗位职责、技术栈、经验要求等\n\n即使只有一句话也没关系，AI 会自动增强补充`} />
          </Form.Item>
          <Form.Item name="created_by" label="创建人">
            <Input placeholder="你的姓名" style={{ width: 200 }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} size="large" block icon={<RocketOutlined />}>
            🧠 启动 AI 增强生成
          </Button>
          <Paragraph type="secondary" style={{ textAlign: 'center', margin: 0, fontSize: 12 }}>
            AI 会自动分析需求、补充缺失信息、RAG 检索相似 JD，直接生成专业岗位描述
          </Paragraph>
        </Space>
      </Form>
    </Card>
  );

  const renderRunning = () => (
    <Card>
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
        <Paragraph style={{ marginTop: 16, color: '#666' }}>
          <RobotOutlined style={{ marginRight: 8 }} />
          AI 正在增强需求并生成 JD...
        </Paragraph>
        <div style={{ marginTop: 12 }}>
          <Progress
            type="circle"
            percent={100}
            format={() => ''}
            width={60}
            strokeColor="#3b82f6"
          />
        </div>
        <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12 }}>
          即使是模糊需求，AI 也会自动补充完善，通常需要 30-120 秒
        </Paragraph>
      </div>
    </Card>
  );

  const renderCompleted = () => (
    <Card
      title={
        <Space>
          <CheckCircleOutlined style={{ color: '#22c55e' }} />
          <span>AI 已生成 JD</span>
        </Space>
      }
      style={{ borderLeft: '4px solid #22c55e' }}
    >
      <div style={{
        background: '#f9fafb', padding: 16, borderRadius: 8,
        border: '1px solid #e5e7eb', maxHeight: 400, overflow: 'auto',
        whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 13, lineHeight: 1.6,
      }}>
        {jdText || '（JD 内容生成中...）'}
      </div>
      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <Space>
          <Button type="primary" size="large" icon={<CheckCircleOutlined />} onClick={() => navigate('/review-jds')}>
            ✅ 前往人工审查
          </Button>
          <Button onClick={handleReset}>创建另一个岗位</Button>
          {requestId && (
            <Button onClick={() => navigate(`/workflow/${requestId}`)}>查看流程</Button>
          )}
        </Space>
      </div>
    </Card>
  );

  const renderError = () => (
    <Card>
      <div style={{ textAlign: 'center', padding: 40 }}>
        <CloseCircleOutlined style={{ fontSize: 48, color: '#ef4444', marginBottom: 16 }} />
        <Title level={4} type="danger">AI 生成失败</Title>
        {errorMsg && (
          <Paragraph type="secondary" style={{ maxWidth: 500, margin: '0 auto 16px', wordBreak: 'break-all' }}>
            {errorMsg}
          </Paragraph>
        )}
        <Space direction="vertical" style={{ width: '100%', maxWidth: 300 }}>
          <Button type="primary" block onClick={handleReset}>重新填写</Button>
          <Button block icon={<ArrowLeftOutlined />} onClick={() => navigate('/workflows')}>返回流程列表</Button>
        </Space>
      </div>
    </Card>
  );

  const stepMap: Record<string, number> = {
    form: 0, running: 1, completed: 3, error: 0,
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <Title level={3}>
        <RocketOutlined style={{ marginRight: 8, color: '#3b82f6' }} />
        新建岗位需求
      </Title>
      <Paragraph type="secondary">
        填写需求后，AI 将自动分析并补充完整，直接生成专业 JD。即使需求模糊也没关系！
      </Paragraph>

      <Steps
        current={stepMap[step]}
        items={[
          { title: '填写需求', description: '模糊也没关系' },
          { title: 'AI 增强生成', description: '自动补充完善' },
          { title: 'AI 生成 JD', description: 'RAG 知识增强' },
          { title: '提交审查', description: 'HR 审核确认' },
        ]}
        style={{ marginBottom: 24 }}
      />

      {step === 'form' && renderForm()}
      {step === 'running' && renderRunning()}
      {step === 'completed' && renderCompleted()}
      {step === 'error' && renderError()}
    </div>
  );
};

export default NewRequest;
