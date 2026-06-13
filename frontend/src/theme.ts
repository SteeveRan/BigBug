import { theme as antdTheme } from 'antd';
import type { ThemeConfig } from 'antd';

/**
 * @file theme.ts
 * @description Тёмная и светлая темы BigBug с брендированными цветами.
 *              Primary: #7C3AED (сливовый — цвет хитинового панциря жука).
 *              По умолчанию используется тёмная тема.
 * @dependencies antd
 * @relatedFiles ThemeContext.tsx, App.tsx, colors.css
 */

// ═══════════════════════════════════════════════════════════════
// Shared typography & shape tokens
// ═══════════════════════════════════════════════════════════════

const sharedToken = {
  borderRadius: 6,
  borderRadiusLG: 8,
  borderRadiusSM: 4,
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: 14,
  lineHeight: 1.5715,
  wireframe: false,
} as const;

// ═══════════════════════════════════════════════════════════════
// Dark Theme (default)
// ═══════════════════════════════════════════════════════════════

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,

  token: {
    // ── Primary palette ──────────────────────────────────
    colorPrimary: '#7C3AED',
    colorPrimaryBg: '#1A1030',
    colorPrimaryBgHover: '#251845',
    colorPrimaryBorder: '#5B21B6',
    colorPrimaryHover: '#8B5CF6',
    colorPrimaryActive: '#6D28D9',
    colorPrimaryText: '#A78BFA',
    colorPrimaryTextHover: '#C4B5FD',

    // ── Semantic ─────────────────────────────────────────
    colorSuccess: '#10B981',
    colorWarning: '#F59E0B',
    colorError: '#EF4444',
    colorInfo: '#3B82F6',

    // ── Neutral / Surface ────────────────────────────────
    colorBgBase: '#0F0F1A',
    colorBgContainer: '#1A1A2E',
    colorBgElevated: '#25253E',
    colorBgLayout: '#0A0A14',

    colorBorder: '#2D2D45',
    colorBorderSecondary: '#1E1E32',

    // ── Text ─────────────────────────────────────────────
    colorText: '#F1F0FB',
    colorTextSecondary: '#A0A0B8',
    colorTextTertiary: '#6B6B85',
    colorTextQuaternary: '#484860',

    // ── Typography ───────────────────────────────────────
    ...sharedToken,
  },

  components: {
    Menu: {
      darkItemBg: '#0A0A14',
      darkItemColor: '#A0A0B8',
      darkItemHoverBg: 'rgba(124, 58, 237, 0.12)',
      darkItemHoverColor: '#C4B5FD',
      darkItemSelectedBg: 'rgba(124, 58, 237, 0.20)',
      darkItemSelectedColor: '#A78BFA',
      darkSubMenuItemBg: '#0A0A14',
      darkGroupTitleColor: '#6B6B85',
      darkItemDisabledColor: '#484860',
      itemHeight: 40,
      itemMarginInline: 8,
      itemBorderRadius: 6,
      groupTitleFontSize: 11,
      groupTitleLineHeight: 1.5,
    },

    Layout: {
      siderBg: '#0A0A14',
      headerBg: '#1A1A2E',
      headerColor: '#F1F0FB',
      bodyBg: '#0F0F1A',
      triggerBg: '#1A1A2E',
      triggerColor: '#A0A0B8',
    },

    Card: {
      colorBgContainer: '#1A1A2E',
    },

    Table: {
      headerBg: '#25253E',
      rowHoverBg: 'rgba(124, 58, 237, 0.04)',
      borderColor: '#2D2D45',
    },

    Tag: {
      defaultBg: '#25253E',
      defaultColor: '#A0A0B8',
    },

    Button: {
      primaryShadow: '0 2px 0 rgba(124, 58, 237, 0.15)',
      dangerShadow: '0 2px 0 rgba(239, 68, 68, 0.15)',
    },
  },
};

// ═══════════════════════════════════════════════════════════════
// Light Theme
// ═══════════════════════════════════════════════════════════════

export const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,

  token: {
    // ── Primary palette ──────────────────────────────────
    colorPrimary: '#7C3AED',
    colorPrimaryBg: '#F5F3FF',
    colorPrimaryBgHover: '#EDE9FE',
    colorPrimaryBorder: '#C4B5FD',
    colorPrimaryHover: '#6D28D9',
    colorPrimaryActive: '#5B21B6',
    colorPrimaryText: '#6D28D9',
    colorPrimaryTextHover: '#5B21B6',

    // ── Semantic ─────────────────────────────────────────
    colorSuccess: '#059669',
    colorWarning: '#D97706',
    colorError: '#DC2626',
    colorInfo: '#2563EB',

    // ── Neutral / Surface ────────────────────────────────
    colorBgBase: '#FAFAFE',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#F3F0F8',

    colorBorder: '#E5E0F0',
    colorBorderSecondary: '#F0EDF5',

    // ── Text ─────────────────────────────────────────────
    colorText: '#1A1A2E',
    colorTextSecondary: '#5C5C78',
    colorTextTertiary: '#8B8BA0',
    colorTextQuaternary: '#B8B8C8',

    // ── Typography ───────────────────────────────────────
    ...sharedToken,
  },

  components: {
    Menu: {
      itemBg: '#FFFFFF',
      itemColor: '#5C5C78',
      itemHoverBg: '#F5F3FF',
      itemHoverColor: '#7C3AED',
      itemSelectedBg: '#EDE9FE',
      itemSelectedColor: '#7C3AED',
      subMenuItemBg: '#FFFFFF',
      groupTitleColor: '#8B8BA0',
    },

    Layout: {
      siderBg: '#F3F0F8',
      headerBg: '#FFFFFF',
      headerColor: '#1A1A2E',
      bodyBg: '#FAFAFE',
      triggerBg: '#F3F0F8',
      triggerColor: '#5C5C78',
    },

    Card: {
      colorBgContainer: '#FFFFFF',
    },
  },
};

/**
 * Дефолтная тема — тёмная.
 * Используется в ThemeContext как начальное значение.
 */
const theme: ThemeConfig = darkTheme;

export default theme;
