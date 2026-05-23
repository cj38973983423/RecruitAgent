import React from 'react';
import { Empty, Button, Space, Typography } from 'antd';
import {
  FileSearchOutlined, TeamOutlined, ScheduleOutlined,
  CloudUploadOutlined, ProfileOutlined, CheckCircleOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;

interface Step {
  icon: React.ReactNode;
  label: string;
}

interface EmptyGuideProps {
  title?: string;
  description?: string;
  steps?: Step[];
  actionText?: string;
  actionLink?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

const stepIcons: Record<string, React.ReactNode> = {
  upload: <CloudUploadOutlined style={{ fontSize: 18, color: '#1677ff' }} />,
  jd: <ProfileOutlined style={{ fontSize: 18, color: '#52c41a' }} />,
  review: <FileSearchOutlined style={{ fontSize: 18, color: '#faad14' }} />,
  interview: <TeamOutlined style={{ fontSize: 18, color: '#8b5cf6' }} />,
  schedule: <ScheduleOutlined style={{ fontSize: 18, color: '#10b981' }} />,
  approve: <CheckCircleOutlined style={{ fontSize: 18, color: '#1677ff' }} />,
};

const EmptyGuide: React.FC<EmptyGuideProps> = ({
  title,
  description,
  steps,
  actionText,
  onAction,
}) => {
  const defaultImage = (
    <div style={{ fontSize: 48, opacity: 0.3, marginBottom: 4 }}>📋</div>
  );

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '48px 24px',
      background: '#fafafa',
      borderRadius: 12,
      border: '1px dashed #d9d9d9',
    }}>
      <Empty
        image={defaultImage}
        imageStyle={{ height: 60 }}
        description={null}
      />
      {title && (
        <Title level={5} style={{ margin: '8px 0 4px', color: '#666' }}>
          {title}
        </Title>
      )}
      {description && (
        <Text type="secondary" style={{ fontSize: 13, textAlign: 'center', maxWidth: 360, lineHeight: 1.8 }}>
          {description}
        </Text>
      )}

      {steps && steps.length > 0 && (
        <div style={{
          display: 'flex',
          gap: 24,
          marginTop: 20,
          flexWrap: 'wrap',
          justifyContent: 'center',
        }}>
          {steps.map((step, idx) => (
            <div key={idx} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: '#fff',
              padding: '8px 16px',
              borderRadius: 8,
              border: '1px solid #e8e8e8',
            }}>
              <div style={{
                width: 24, height: 24, borderRadius: 12,
                background: '#1677ff', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 'bold', flexShrink: 0,
              }}>
                {idx + 1}
              </div>
              {step.icon && <span style={{ marginLeft: 4 }}>{step.icon}</span>}
              <Text style={{ fontSize: 13, whiteSpace: 'nowrap' }}>{step.label}</Text>
            </div>
          ))}
        </div>
      )}

      {actionText && onAction && (
        <Button type="primary" onClick={onAction} style={{ marginTop: 20 }}>
          {actionText}
        </Button>
      )}
    </div>
  );
};

export { EmptyGuide, stepIcons };
export type { EmptyGuideProps, Step };
