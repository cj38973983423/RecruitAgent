import type { ThemeConfig } from 'antd';

export interface ThemePreset {
  key: string;
  label: string;
  icon: string;
  config: ThemeConfig;
}

// ─── 主题预设 ───

const themes: ThemePreset[] = [
  {
    key: 'ocean',
    label: '碧海蓝',
    icon: '🌊',
    config: {
      token: {
        colorPrimary: '#2563eb',
        colorInfo: '#2563eb',
        colorSuccess: '#10b981',
        colorWarning: '#f59e0b',
        colorError: '#ef4444',
        borderRadius: 8,
        colorBgContainer: '#ffffff',
        colorBgLayout: '#f0f5ff',
        colorBgElevated: '#ffffff',
        colorBorder: '#e2e8f0',
        colorText: '#1e293b',
        colorTextSecondary: '#64748b',
        fontSize: 14,
        wireframe: false,
      },
      components: {
        Layout: {
          siderBg: '#ffffff',
          headerBg: '#ffffff',
          bodyBg: '#f0f5ff',
        },
        Menu: {
          itemBg: 'transparent',
          itemColor: '#475569',
          itemSelectedBg: '#eff6ff',
          itemSelectedColor: '#2563eb',
          itemHoverBg: '#f1f5f9',
          itemHoverColor: '#2563eb',
          itemBorderRadius: 8,
          itemMarginInline: 8,
        },
        Card: {
          paddingLG: 20,
        },
        Table: {
          headerBg: '#f8fafc',
          headerColor: '#475569',
          rowHoverBg: '#f1f5f9',
          borderColor: '#e2e8f0',
        },
        Tag: {
          defaultBg: '#f1f5f9',
          defaultColor: '#475569',
        },
        Button: {
          primaryShadow: '0 1px 2px 0 rgba(37, 99, 235, 0.3)',
        },
      },
    },
  },
  {
    key: 'bamboo',
    label: '青竹绿',
    icon: '🎋',
    config: {
      token: {
        colorPrimary: '#059669',
        colorInfo: '#059669',
        colorSuccess: '#10b981',
        colorWarning: '#d97706',
        colorError: '#dc2626',
        borderRadius: 10,
        colorBgContainer: '#ffffff',
        colorBgLayout: '#ecfdf5',
        colorBgElevated: '#ffffff',
        colorBorder: '#d1d5db',
        colorText: '#1f2937',
        colorTextSecondary: '#6b7280',
        fontSize: 14,
        wireframe: false,
      },
      components: {
        Layout: {
          siderBg: '#ffffff',
          headerBg: '#ffffff',
          bodyBg: '#ecfdf5',
        },
        Menu: {
          itemBg: 'transparent',
          itemColor: '#4b5563',
          itemSelectedBg: '#d1fae5',
          itemSelectedColor: '#059669',
          itemHoverBg: '#f0fdf4',
          itemHoverColor: '#059669',
          itemBorderRadius: 8,
          itemMarginInline: 8,
        },
        Card: {
          paddingLG: 20,
        },
        Table: {
          headerBg: '#f0fdf4',
          headerColor: '#374151',
          rowHoverBg: '#f0fdf4',
          borderColor: '#d1d5db',
        },
        Tag: {
          defaultBg: '#f0fdf4',
          defaultColor: '#374151',
        },
        Button: {
          primaryShadow: '0 1px 2px 0 rgba(5, 150, 105, 0.3)',
        },
      },
    },
  },
  {
    key: 'twilight',
    label: '暮光紫',
    icon: '🌆',
    config: {
      token: {
        colorPrimary: '#7c3aed',
        colorInfo: '#7c3aed',
        colorSuccess: '#10b981',
        colorWarning: '#f59e0b',
        colorError: '#ef4444',
        borderRadius: 10,
        colorBgContainer: '#ffffff',
        colorBgLayout: '#f5f3ff',
        colorBgElevated: '#ffffff',
        colorBorder: '#e5e7eb',
        colorText: '#1f2937',
        colorTextSecondary: '#6b7280',
        fontSize: 14,
        wireframe: false,
      },
      components: {
        Layout: {
          siderBg: '#ffffff',
          headerBg: '#ffffff',
          bodyBg: '#f5f3ff',
        },
        Menu: {
          itemBg: 'transparent',
          itemColor: '#4b5563',
          itemSelectedBg: '#ede9fe',
          itemSelectedColor: '#7c3aed',
          itemHoverBg: '#f5f3ff',
          itemHoverColor: '#7c3aed',
          itemBorderRadius: 8,
          itemMarginInline: 8,
        },
        Card: {
          paddingLG: 20,
        },
        Table: {
          headerBg: '#f5f3ff',
          headerColor: '#374151',
          rowHoverBg: '#f5f3ff',
          borderColor: '#e5e7eb',
        },
        Tag: {
          defaultBg: '#f5f3ff',
          defaultColor: '#374151',
        },
        Button: {
          primaryShadow: '0 1px 2px 0 rgba(124, 58, 237, 0.3)',
        },
      },
    },
  },
  {
    key: 'midnight',
    label: '暗夜黑',
    icon: '🌙',
    config: {
      token: {
        colorPrimary: '#818cf8',
        colorInfo: '#818cf8',
        colorSuccess: '#34d399',
        colorWarning: '#fbbf24',
        colorError: '#f87171',
        borderRadius: 8,
        colorBgContainer: '#1e293b',
        colorBgLayout: '#0f172a',
        colorBgElevated: '#1e293b',
        colorBorder: '#334155',
        colorText: '#e2e8f0',
        colorTextSecondary: '#94a3b8',
        colorBgMask: 'rgba(0,0,0,0.6)',
        fontSize: 14,
        wireframe: false,
      },
      components: {
        Layout: {
          siderBg: '#1e293b',
          headerBg: '#1e293b',
          bodyBg: '#0f172a',
          triggerBg: '#334155',
        },
        Menu: {
          itemBg: 'transparent',
          itemColor: '#94a3b8',
          itemSelectedBg: '#334155',
          itemSelectedColor: '#818cf8',
          itemHoverBg: '#1e293b',
          itemHoverColor: '#e2e8f0',
          itemBorderRadius: 8,
          itemMarginInline: 8,
        },
        Card: {
          paddingLG: 20,
          colorBorderSecondary: '#334155',
        },
        Table: {
          headerBg: '#1e293b',
          headerColor: '#94a3b8',
          rowHoverBg: '#334155',
          borderColor: '#334155',
          colorBgContainer: '#1e293b',
        },
        Tag: {
          defaultBg: '#334155',
          defaultColor: '#94a3b8',
        },
        Button: {
          primaryShadow: '0 1px 2px 0 rgba(129, 140, 248, 0.3)',
        },
        Modal: {
          contentBg: '#1e293b',
          headerBg: '#1e293b',
          footerBg: '#1e293b',
        },
        Input: {
          colorBgContainer: '#0f172a',
          colorBorder: '#334155',
          activeBorderColor: '#818cf8',
          hoverBorderColor: '#6366f1',
        },
        Select: {
          colorBgContainer: '#0f172a',
          colorBorder: '#334155',
          optionSelectedBg: '#334155',
        },
        DatePicker: {
          colorBgContainer: '#0f172a',
          colorBorder: '#334155',
          activeBorderColor: '#818cf8',
        },
        Message: {
          contentBg: '#1e293b',
        },
      },
    },
  },
];

export default themes;
