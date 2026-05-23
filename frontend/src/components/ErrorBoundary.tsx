import React from 'react';
import { Button, Typography, Space, Divider } from 'antd';
import { WarningOutlined, ReloadOutlined, HomeOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

interface Props {
  children: React.ReactNode;
  /** 页面名称，用于错误提示更友好 */
  pageName?: string;
  /** 是否在出错时显示返回首页按钮 */
  showHome?: boolean;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(`[ErrorBoundary${this.props.pageName ? ` - ${this.props.pageName}` : ''}]`, error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      const pageLabel = this.props.pageName || '此页面';
      return (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 300,
          padding: 48,
        }}>
          <div style={{
            textAlign: 'center',
            maxWidth: 480,
            background: '#fff',
            borderRadius: 12,
            padding: '40px 32px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          }}>
            <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.4 }}>
              <WarningOutlined style={{ color: '#faad14' }} />
            </div>
            <Title level={4} style={{ marginBottom: 8 }}>
              😅 {pageLabel} 出了点小状况
            </Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
              一个意外错误导致 {pageLabel} 无法正常显示
            </Text>
            {this.state.error && (
              <>
                <Divider style={{ margin: '12px 0' }} />
                <Paragraph
                  style={{
                    fontSize: 12,
                    color: '#999',
                    textAlign: 'left',
                    background: '#fafafa',
                    padding: '8px 12px',
                    borderRadius: 6,
                    maxHeight: 200,
                    overflow: 'auto',
                    wordBreak: 'break-all',
                  }}
                  copyable={{ text: this.state.error.stack || this.state.error.message }}
                >
                  {this.state.error.stack || this.state.error.message}
                </Paragraph>
              </>
            )}
            <Space size="middle" style={{ marginTop: 16 }}>
              <Button type="primary" icon={<ReloadOutlined />} onClick={this.handleReset}>
                重新加载
              </Button>
              {this.props.showHome && (
                <Button icon={<HomeOutlined />} onClick={this.handleGoHome}>
                  返回首页
                </Button>
              )}
            </Space>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
