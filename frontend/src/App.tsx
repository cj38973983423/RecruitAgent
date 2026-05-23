import React, { useState } from 'react';
import { Layout, Menu, ConfigProvider, Typography, Divider } from 'antd';
import {
  ApartmentOutlined, RocketOutlined, FileTextOutlined,
  UserOutlined, ScheduleOutlined, DashboardOutlined,
  TeamOutlined, PlusOutlined, DatabaseOutlined, AuditOutlined,
  BgColorsOutlined, DollarOutlined, CheckCircleOutlined, StarOutlined,
} from '@ant-design/icons';
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import zhCN from 'antd/locale/zh_CN';

import WorkflowView from './pages/WorkflowView';
import WorkflowList from './pages/WorkflowList';
import NewRequest from './pages/NewRequest';
import JDManage from './pages/JDManage';
import JDReviewPage from './pages/JDReviewPage';
import ResumeManage from './pages/ResumeManage';
import InterviewManage from './pages/InterviewManage';
import Dashboard from './pages/Dashboard';
import KnowledgeBase from './pages/KnowledgeBase';
import InterviewerManage from './pages/InterviewerManage';
import OfferManage from './pages/OfferManage';
import OnboardingManage from './pages/OnboardingManage';
import CandidatesManage from './pages/CandidatesManage';
import ErrorBoundary from './components/ErrorBoundary';
import themes from './themes';
import type { ThemePreset } from './themes';

const { Sider, Content } = Layout;
const { Text } = Typography;

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const savedTheme = localStorage.getItem('recruit_theme') || 'ocean';
  const [currentTheme, setCurrentTheme] = useState<ThemePreset>(
    themes.find(t => t.key === savedTheme) || themes[0]
  );
  const [showThemePicker, setShowThemePicker] = useState(false);
  const isDark = currentTheme.key === 'midnight';

  const switchTheme = (theme: ThemePreset) => {
    setCurrentTheme(theme);
    localStorage.setItem('recruit_theme', theme.key);
    setShowThemePicker(false);
  };

  const selectedKey = location.pathname.split('/')[1] || 'dashboard';

  const menuItems = [
    {
      type: 'group' as const,
      label: <span style={{ fontSize: 11, color: isDark ? '#64748b' : '#94a3b8', letterSpacing: 1, paddingLeft: 4 }}>📊 总览</span>,
      children: [
        { key: 'dashboard', icon: <DashboardOutlined />, label: '数据看板' },
      ],
    },
    {
      type: 'group' as const,
      label: <span style={{ fontSize: 11, color: isDark ? '#64748b' : '#94a3b8', letterSpacing: 1, paddingLeft: 4 }}>📋 需求管理</span>,
      children: [
        { key: 'new', icon: <PlusOutlined />, label: '新建岗位' },
        { key: 'workflows', icon: <ApartmentOutlined />, label: '岗位生成流程' },
        { key: 'review-jds', icon: <AuditOutlined />, label: '岗位人工审查' },
        { key: 'jds', icon: <FileTextOutlined />, label: '岗位管理' },
      ],
    },
    {
      type: 'group' as const,
      label: <span style={{ fontSize: 11, color: isDark ? '#64748b' : '#94a3b8', letterSpacing: 1, paddingLeft: 4 }}>👥 筛选与候选人</span>,
      children: [
        { key: 'resumes', icon: <UserOutlined />, label: '简历管理' },
      ],
    },
    {
      type: 'group' as const,
      label: <span style={{ fontSize: 11, color: isDark ? '#64748b' : '#94a3b8', letterSpacing: 1, paddingLeft: 4 }}>🎯 面试管理</span>,
      children: [
        { key: 'interviews', icon: <ScheduleOutlined />, label: '面试管理' },
        { key: 'interviewers', icon: <TeamOutlined />, label: '面试官库' },
      ],
    },
    {
      type: 'group' as const,
      label: <span style={{ fontSize: 11, color: isDark ? '#64748b' : '#94a3b8', letterSpacing: 1, paddingLeft: 4 }}>📄 录用管理</span>,
      children: [
        { key: 'candidates', icon: <StarOutlined />, label: '候选人库' },
        { key: 'offers', icon: <DollarOutlined />, label: 'Offer管理' },
        { key: 'onboarding', icon: <CheckCircleOutlined />, label: '入职管理' },
      ],
    },
    {
      type: 'group' as const,
      label: <span style={{ fontSize: 11, color: isDark ? '#64748b' : '#94a3b8', letterSpacing: 1, paddingLeft: 4 }}>⚙️ 基础配置</span>,
      children: [
        { key: 'kb', icon: <DatabaseOutlined />, label: '知识库' },
      ],
    },
  ];

  const onMenuClick = (e: { key: string }) => {
    navigate(`/${e.key}`);
  };

  // 页面路由
  const routeContent = (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<ErrorBoundary pageName="数据看板"><Dashboard /></ErrorBoundary>} />
      <Route path="/new" element={<ErrorBoundary pageName="新建岗位"><NewRequest /></ErrorBoundary>} />
      <Route path="/workflows" element={<ErrorBoundary pageName="岗位生成流程"><WorkflowList /></ErrorBoundary>} />
      <Route path="/workflow/:id" element={<ErrorBoundary pageName="工作流详情"><WorkflowView /></ErrorBoundary>} />
      <Route path="/review-jds" element={<ErrorBoundary pageName="岗位审查"><JDReviewPage /></ErrorBoundary>} />
      <Route path="/jds" element={<ErrorBoundary pageName="岗位管理"><JDManage /></ErrorBoundary>} />
      <Route path="/kb" element={<ErrorBoundary pageName="知识库"><KnowledgeBase /></ErrorBoundary>} />
      <Route path="/resumes" element={<ErrorBoundary pageName="简历管理"><ResumeManage /></ErrorBoundary>} />
      <Route path="/candidates" element={<ErrorBoundary pageName="候选人库"><CandidatesManage /></ErrorBoundary>} />
      <Route path="/interviews" element={<ErrorBoundary pageName="面试管理"><InterviewManage /></ErrorBoundary>} />
      <Route path="/interviewers" element={<ErrorBoundary pageName="面试官库"><InterviewerManage /></ErrorBoundary>} />
      <Route path="/offers" element={<ErrorBoundary pageName="Offer管理"><OfferManage /></ErrorBoundary>} />
      <Route path="/onboarding" element={<ErrorBoundary pageName="入职管理"><OnboardingManage /></ErrorBoundary>} />
    </Routes>
  );

  const siderBg = currentTheme.config.components?.Layout?.siderBg as string || '#fff';

  return (
    <ConfigProvider locale={zhCN} theme={currentTheme.config}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          width={220}
          collapsedWidth={64}
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme={isDark ? 'dark' : 'light'}
          style={{
            borderRight: isDark ? '1px solid #334155' : '1px solid #f0f0f0',
            position: 'sticky',
            top: 0,
            height: '100vh',
            overflow: 'auto',
          }}
        >
          {/* Logo */}
          <div style={{
            padding: collapsed ? '16px 0' : '20px 16px',
            borderBottom: isDark ? '1px solid #334155' : '1px solid #f0f0f0',
            textAlign: collapsed ? 'center' : 'left',
            transition: 'padding 0.2s',
          }}>
            <Text strong style={{
              fontSize: collapsed ? 20 : 18,
              color: currentTheme.config.token?.colorPrimary,
              whiteSpace: 'nowrap',
            }}>
              <RocketOutlined style={{ marginRight: collapsed ? 0 : 8 }} />
              {!collapsed && 'RecruitAgent'}
            </Text>
          </div>

          {/* 导航菜单 */}
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={onMenuClick}
            style={{
              borderRight: 0,
              marginTop: 4,
              background: 'transparent',
            }}
          />

          <Divider style={{ margin: '8px 16px', minWidth: 'auto', width: 'auto' }} />

          {/* 主题切换 */}
          <div style={{ padding: collapsed ? '8px 12px' : '8px 16px' }}>
            <div
              onClick={() => {
                if (collapsed) {
                  // 折叠态：直接轮换主题
                  const idx = themes.findIndex(t => t.key === currentTheme.key);
                  const next = themes[(idx + 1) % themes.length];
                  switchTheme(next);
                } else {
                  setShowThemePicker(!showThemePicker);
                }
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 12px',
                borderRadius: 8,
                cursor: collapsed ? 'pointer' : 'pointer',
                color: isDark ? '#94a3b8' : '#64748b',
                fontSize: 13,
                justifyContent: collapsed ? 'center' : 'flex-start',
                transition: 'background 0.2s',
              }}
              className="sidebar-theme-btn"
              title="切换主题"
            >
              <BgColorsOutlined style={{ fontSize: 16 }} />
              {!collapsed && (
                <span style={{ flex: 1 }}>
                  {currentTheme.icon} {currentTheme.label}
                </span>
              )}
              {!collapsed && (
                <span style={{ fontSize: 10, opacity: 0.5 }}>▼</span>
              )}
            </div>

            {/* 主题选择面板 */}
            {showThemePicker && !collapsed && (
              <div style={{
                marginTop: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                padding: '4px 0',
              }}>
                {themes.map(t => (
                  <div
                    key={t.key}
                    onClick={() => switchTheme(t)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 12px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      background: t.key === currentTheme.key
                        ? (isDark ? '#334155' : '#f1f5f9')
                        : 'transparent',
                      color: t.key === currentTheme.key
                        ? currentTheme.config.token?.colorPrimary
                        : (isDark ? '#94a3b8' : '#64748b'),
                      fontWeight: t.key === currentTheme.key ? 600 : 400,
                      fontSize: 13,
                      transition: 'all 0.15s',
                    }}
                    className="theme-option"
                  >
                    <span style={{ fontSize: 16 }}>{t.icon}</span>
                    <span>{t.label}</span>
                    {t.key === currentTheme.key && (
                      <span style={{ marginLeft: 'auto', fontSize: 12 }}>✓</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Sider>

        <Layout>
          <Content style={{
            padding: 24,
            minHeight: 'calc(100vh - 48px)',
            overflow: 'auto',
          }}>
            <ErrorBoundary showHome>
              {routeContent}
            </ErrorBoundary>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
};

export default App;
