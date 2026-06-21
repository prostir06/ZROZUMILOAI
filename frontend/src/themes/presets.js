export const THEME_STORAGE_KEY = 'zrozumiloai-theme';

export const DEFAULT_PRESET_ID = 'light';

const LIGHT_BODY_BACKGROUND = `radial-gradient(circle 962px at -450px 46px, rgba(26, 203, 195, 0.4) 0%, rgba(26, 203, 195, 0) 100%), radial-gradient(circle 962px at 985px 1205px, rgba(26, 203, 195, 0.4) 0%, rgba(26, 203, 195, 0) 100%), radial-gradient(circle 962px at -450px 2279px, rgba(26, 203, 195, 0.4) 0%, rgba(26, 203, 195, 0) 100%), #EBF4F3`;

function buildEllipseBodyBackground(vars) {
  return `radial-gradient(ellipse 80% 60% at 10% 0%, ${vars['--gradient-spot-1']}, transparent), radial-gradient(ellipse 70% 50% at 90% 10%, ${vars['--gradient-spot-2']}, transparent), radial-gradient(ellipse 60% 40% at 50% 100%, ${vars['--gradient-spot-3']}, transparent), linear-gradient(160deg, ${vars['--gradient-linear-start']} 0%, ${vars['--gradient-linear-mid']} 45%, ${vars['--gradient-linear-end']} 100%)`;
}

const baseStructure = {
  '--radius': '10px',
  '--radius-lg': '16px',
  '--glass-blur': 'blur(18px)',
  '--color-danger': '#ef4444',
  '--color-success': '#16a34a',
  '--color-warning': '#d97706',
};

export const THEME_PRESETS = {
  light: {
    id: 'light',
    name: 'Світла',
    preview: ['#EBF4F3', '#0D9E96', '#ffffff'],
    vars: {
      ...baseStructure,
      '--color-bg': '#EBF4F3',
      '--color-surface': 'rgba(255, 255, 255, 0.55)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.84)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.74)',
      '--color-border': 'rgba(255, 255, 255, 0.68)',
      '--color-border-subtle': 'rgba(13, 158, 150, 0.14)',
      '--color-text': '#1C3D3A',
      '--color-text-muted': '#5E7A78',
      '--color-primary': '#0D9E96',
      '--color-primary-hover': '#0B857E',
      '--color-primary-soft': 'rgba(26, 203, 195, 0.14)',
      '--shadow': '0 8px 32px rgba(26, 203, 195, 0.1)',
      '--shadow-soft': '0 2px 16px rgba(20, 80, 75, 0.06)',
      '--gradient-spot-1': 'rgba(26, 203, 195, 0.35)',
      '--gradient-spot-2': 'rgba(78, 205, 196, 0.28)',
      '--gradient-spot-3': 'rgba(167, 243, 239, 0.32)',
      '--gradient-linear-start': '#F4FBFA',
      '--gradient-linear-mid': '#EBF4F3',
      '--gradient-linear-end': '#E0F5F3',
      '--input-bg': 'rgba(255, 255, 255, 0.58)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.88)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.48)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.78)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.64)',
      '--chat-user-start': 'rgba(78, 205, 196, 0.95)',
      '--chat-user-end': 'rgba(13, 158, 150, 0.95)',
      '--body-background': LIGHT_BODY_BACKGROUND,
    },
  },
  dark: {
    id: 'dark',
    name: 'Темна',
    preview: ['#0f172a', '#818cf8', '#1e293b'],
    vars: {
      ...baseStructure,
      '--color-bg': '#0f172a',
      '--color-surface': 'rgba(30, 41, 59, 0.65)',
      '--color-surface-solid': 'rgba(30, 41, 59, 0.88)',
      '--color-surface-hover': 'rgba(51, 65, 85, 0.75)',
      '--color-border': 'rgba(148, 163, 184, 0.15)',
      '--color-border-subtle': 'rgba(148, 163, 184, 0.12)',
      '--color-text': '#f1f5f9',
      '--color-text-muted': '#94a3b8',
      '--color-primary': '#818cf8',
      '--color-primary-hover': '#a5b4fc',
      '--color-primary-soft': 'rgba(129, 140, 248, 0.18)',
      '--shadow': '0 8px 32px rgba(0, 0, 0, 0.35)',
      '--shadow-soft': '0 2px 16px rgba(0, 0, 0, 0.25)',
      '--gradient-spot-1': 'rgba(99, 102, 241, 0.2)',
      '--gradient-spot-2': 'rgba(56, 189, 248, 0.12)',
      '--gradient-spot-3': 'rgba(167, 139, 250, 0.15)',
      '--gradient-linear-start': '#0f172a',
      '--gradient-linear-mid': '#1e1b4b',
      '--gradient-linear-end': '#0f172a',
      '--input-bg': 'rgba(15, 23, 42, 0.6)',
      '--input-bg-focus': 'rgba(30, 41, 59, 0.9)',
      '--btn-ghost-bg': 'rgba(30, 41, 59, 0.5)',
      '--btn-ghost-hover': 'rgba(51, 65, 85, 0.8)',
      '--chat-assistant-bg': 'rgba(30, 41, 59, 0.75)',
      '--chat-user-start': 'rgba(99, 102, 241, 0.95)',
      '--chat-user-end': 'rgba(79, 70, 229, 0.95)',
    },
  },
  oled: {
    id: 'oled',
    name: 'OLED',
    preview: ['#000000', '#6EE7B7', '#0A0A0A'],
    vars: {
      ...baseStructure,
      '--glass-blur': 'none',
      '--color-bg': '#000000',
      '--color-surface': 'rgba(10, 10, 10, 0.92)',
      '--color-surface-solid': '#0A0A0A',
      '--color-surface-hover': '#141414',
      '--color-border': 'rgba(255, 255, 255, 0.08)',
      '--color-border-subtle': 'rgba(255, 255, 255, 0.05)',
      '--color-text': '#F5F5F5',
      '--color-text-muted': '#737373',
      '--color-primary': '#6EE7B7',
      '--color-primary-hover': '#A7F3D0',
      '--color-primary-soft': 'rgba(110, 231, 183, 0.12)',
      '--shadow': 'none',
      '--shadow-soft': 'none',
      '--gradient-spot-1': 'rgba(0, 0, 0, 0)',
      '--gradient-spot-2': 'rgba(0, 0, 0, 0)',
      '--gradient-spot-3': 'rgba(0, 0, 0, 0)',
      '--gradient-linear-start': '#000000',
      '--gradient-linear-mid': '#000000',
      '--gradient-linear-end': '#000000',
      '--input-bg': '#0A0A0A',
      '--input-bg-focus': '#111111',
      '--btn-ghost-bg': '#0A0A0A',
      '--btn-ghost-hover': '#1A1A1A',
      '--chat-assistant-bg': '#0A0A0A',
      '--chat-user-start': 'rgba(52, 211, 153, 0.85)',
      '--chat-user-end': 'rgba(16, 185, 129, 0.85)',
      '--body-background': '#000000',
    },
  },
  ocean: {
    id: 'ocean',
    name: 'Океан',
    preview: ['#e0f2fe', '#0891b2', '#f0fdfa'],
    vars: {
      ...baseStructure,
      '--color-bg': '#e0f2fe',
      '--color-surface': 'rgba(255, 255, 255, 0.5)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.82)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.72)',
      '--color-border': 'rgba(255, 255, 255, 0.6)',
      '--color-border-subtle': 'rgba(6, 182, 212, 0.2)',
      '--color-text': '#0c4a6e',
      '--color-text-muted': '#0369a1',
      '--color-primary': '#0891b2',
      '--color-primary-hover': '#0e7490',
      '--color-primary-soft': 'rgba(8, 145, 178, 0.14)',
      '--shadow': '0 8px 32px rgba(8, 145, 178, 0.1)',
      '--shadow-soft': '0 2px 16px rgba(8, 145, 178, 0.06)',
      '--gradient-spot-1': 'rgba(125, 211, 252, 0.5)',
      '--gradient-spot-2': 'rgba(153, 246, 228, 0.45)',
      '--gradient-spot-3': 'rgba(186, 230, 253, 0.4)',
      '--gradient-linear-start': '#f0f9ff',
      '--gradient-linear-mid': '#e0f2fe',
      '--gradient-linear-end': '#ecfeff',
      '--input-bg': 'rgba(255, 255, 255, 0.55)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.88)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.45)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.75)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.65)',
      '--chat-user-start': 'rgba(34, 211, 238, 0.9)',
      '--chat-user-end': 'rgba(8, 145, 178, 0.9)',
    },
  },
  forest: {
    id: 'forest',
    name: 'Ліс',
    preview: ['#ecfdf5', '#059669', '#f0fdf4'],
    vars: {
      ...baseStructure,
      '--color-bg': '#ecfdf5',
      '--color-surface': 'rgba(255, 255, 255, 0.52)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.82)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.72)',
      '--color-border': 'rgba(255, 255, 255, 0.6)',
      '--color-border-subtle': 'rgba(5, 150, 105, 0.2)',
      '--color-text': '#064e3b',
      '--color-text-muted': '#047857',
      '--color-primary': '#059669',
      '--color-primary-hover': '#047857',
      '--color-primary-soft': 'rgba(5, 150, 105, 0.14)',
      '--shadow': '0 8px 32px rgba(5, 150, 105, 0.08)',
      '--shadow-soft': '0 2px 16px rgba(5, 150, 105, 0.05)',
      '--gradient-spot-1': 'rgba(167, 243, 208, 0.5)',
      '--gradient-spot-2': 'rgba(187, 247, 208, 0.45)',
      '--gradient-spot-3': 'rgba(209, 250, 229, 0.4)',
      '--gradient-linear-start': '#f0fdf4',
      '--gradient-linear-mid': '#ecfdf5',
      '--gradient-linear-end': '#f7fee7',
      '--input-bg': 'rgba(255, 255, 255, 0.55)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.88)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.45)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.75)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.65)',
      '--chat-user-start': 'rgba(52, 211, 153, 0.9)',
      '--chat-user-end': 'rgba(5, 150, 105, 0.9)',
    },
  },
  sunset: {
    id: 'sunset',
    name: 'Захід',
    preview: ['#fff7ed', '#ea580c', '#fef3c7'],
    vars: {
      ...baseStructure,
      '--color-bg': '#fff7ed',
      '--color-surface': 'rgba(255, 255, 255, 0.55)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.85)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.75)',
      '--color-border': 'rgba(255, 255, 255, 0.65)',
      '--color-border-subtle': 'rgba(234, 88, 12, 0.18)',
      '--color-text': '#7c2d12',
      '--color-text-muted': '#c2410c',
      '--color-primary': '#ea580c',
      '--color-primary-hover': '#c2410c',
      '--color-primary-soft': 'rgba(234, 88, 12, 0.12)',
      '--shadow': '0 8px 32px rgba(234, 88, 12, 0.08)',
      '--shadow-soft': '0 2px 16px rgba(234, 88, 12, 0.05)',
      '--gradient-spot-1': 'rgba(254, 215, 170, 0.55)',
      '--gradient-spot-2': 'rgba(253, 186, 116, 0.45)',
      '--gradient-spot-3': 'rgba(254, 240, 138, 0.4)',
      '--gradient-linear-start': '#fffbeb',
      '--gradient-linear-mid': '#fff7ed',
      '--gradient-linear-end': '#fef2f2',
      '--input-bg': 'rgba(255, 255, 255, 0.55)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.88)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.45)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.75)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.65)',
      '--chat-user-start': 'rgba(251, 146, 60, 0.92)',
      '--chat-user-end': 'rgba(234, 88, 12, 0.92)',
    },
  },
  lavender: {
    id: 'lavender',
    name: 'Лаванда',
    preview: ['#faf5ff', '#9333ea', '#f5f3ff'],
    vars: {
      ...baseStructure,
      '--color-bg': '#faf5ff',
      '--color-surface': 'rgba(255, 255, 255, 0.52)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.82)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.72)',
      '--color-border': 'rgba(255, 255, 255, 0.65)',
      '--color-border-subtle': 'rgba(147, 51, 234, 0.18)',
      '--color-text': '#581c87',
      '--color-text-muted': '#7e22ce',
      '--color-primary': '#9333ea',
      '--color-primary-hover': '#7e22ce',
      '--color-primary-soft': 'rgba(147, 51, 234, 0.12)',
      '--shadow': '0 8px 32px rgba(147, 51, 234, 0.08)',
      '--shadow-soft': '0 2px 16px rgba(147, 51, 234, 0.05)',
      '--gradient-spot-1': 'rgba(233, 213, 255, 0.55)',
      '--gradient-spot-2': 'rgba(216, 180, 254, 0.45)',
      '--gradient-spot-3': 'rgba(245, 208, 254, 0.4)',
      '--gradient-linear-start': '#faf5ff',
      '--gradient-linear-mid': '#f5f3ff',
      '--gradient-linear-end': '#fdf4ff',
      '--input-bg': 'rgba(255, 255, 255, 0.55)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.88)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.45)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.75)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.65)',
      '--chat-user-start': 'rgba(192, 132, 252, 0.92)',
      '--chat-user-end': 'rgba(147, 51, 234, 0.92)',
    },
  },
  gemini: {
    id: 'gemini',
    name: 'Google Gemini',
    preview: ['#F0F4F9', '#1A73E8', '#FFFFFF'],
    vars: {
      ...baseStructure,
      '--color-bg': '#F0F4F9',
      '--color-surface': 'rgba(255, 255, 255, 0.72)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.94)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.86)',
      '--color-border': 'rgba(0, 0, 0, 0.08)',
      '--color-border-subtle': 'rgba(26, 115, 232, 0.16)',
      '--color-text': '#1F1F1F',
      '--color-text-muted': '#5F6368',
      '--color-primary': '#1A73E8',
      '--color-primary-hover': '#1557B0',
      '--color-primary-soft': 'rgba(26, 115, 232, 0.12)',
      '--shadow': '0 8px 32px rgba(26, 115, 232, 0.08)',
      '--shadow-soft': '0 2px 16px rgba(0, 0, 0, 0.04)',
      '--gradient-spot-1': 'rgba(66, 133, 244, 0.18)',
      '--gradient-spot-2': 'rgba(155, 114, 203, 0.14)',
      '--gradient-spot-3': 'rgba(251, 188, 5, 0.1)',
      '--gradient-linear-start': '#FFFFFF',
      '--gradient-linear-mid': '#F0F4F9',
      '--gradient-linear-end': '#E8F0FE',
      '--input-bg': 'rgba(255, 255, 255, 0.88)',
      '--input-bg-focus': '#FFFFFF',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.6)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.9)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.78)',
      '--chat-user-start': 'rgba(66, 133, 244, 0.92)',
      '--chat-user-end': 'rgba(26, 115, 232, 0.92)',
    },
  },
  claude: {
    id: 'claude',
    name: 'Anthropic Claude',
    preview: ['#FAF9F5', '#D97757', '#FFFFFF'],
    vars: {
      ...baseStructure,
      '--color-bg': '#FAF9F5',
      '--color-surface': 'rgba(255, 255, 255, 0.58)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.86)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.76)',
      '--color-border': 'rgba(217, 119, 87, 0.12)',
      '--color-border-subtle': 'rgba(217, 119, 87, 0.18)',
      '--color-text': '#2B2922',
      '--color-text-muted': '#8A8475',
      '--color-primary': '#D97757',
      '--color-primary-hover': '#C4684A',
      '--color-primary-soft': 'rgba(217, 119, 87, 0.14)',
      '--shadow': '0 8px 32px rgba(217, 119, 87, 0.08)',
      '--shadow-soft': '0 2px 16px rgba(43, 41, 34, 0.05)',
      '--gradient-spot-1': 'rgba(217, 119, 87, 0.18)',
      '--gradient-spot-2': 'rgba(245, 230, 211, 0.55)',
      '--gradient-spot-3': 'rgba(237, 224, 205, 0.45)',
      '--gradient-linear-start': '#FFFDF9',
      '--gradient-linear-mid': '#FAF9F5',
      '--gradient-linear-end': '#F4F0E8',
      '--input-bg': 'rgba(255, 255, 255, 0.62)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.92)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.5)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.8)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.68)',
      '--chat-user-start': 'rgba(224, 140, 110, 0.92)',
      '--chat-user-end': 'rgba(217, 119, 87, 0.92)',
    },
  },
  copilot: {
    id: 'copilot',
    name: 'Microsoft Copilot',
    preview: ['#F0F4FA', '#0078D4', '#E8EBFA'],
    vars: {
      ...baseStructure,
      '--color-bg': '#F0F4FA',
      '--color-surface': 'rgba(255, 255, 255, 0.58)',
      '--color-surface-solid': 'rgba(255, 255, 255, 0.88)',
      '--color-surface-hover': 'rgba(255, 255, 255, 0.78)',
      '--color-border': 'rgba(0, 120, 212, 0.14)',
      '--color-border-subtle': 'rgba(91, 95, 199, 0.16)',
      '--color-text': '#242424',
      '--color-text-muted': '#616161',
      '--color-primary': '#0078D4',
      '--color-primary-hover': '#106EBE',
      '--color-primary-soft': 'rgba(0, 120, 212, 0.14)',
      '--shadow': '0 8px 32px rgba(0, 120, 212, 0.1)',
      '--shadow-soft': '0 2px 16px rgba(91, 95, 199, 0.08)',
      '--gradient-spot-1': 'rgba(0, 120, 212, 0.22)',
      '--gradient-spot-2': 'rgba(91, 95, 199, 0.2)',
      '--gradient-spot-3': 'rgba(185, 198, 255, 0.35)',
      '--gradient-linear-start': '#F8FAFF',
      '--gradient-linear-mid': '#F0F4FA',
      '--gradient-linear-end': '#E8EBFA',
      '--input-bg': 'rgba(255, 255, 255, 0.62)',
      '--input-bg-focus': 'rgba(255, 255, 255, 0.94)',
      '--btn-ghost-bg': 'rgba(255, 255, 255, 0.5)',
      '--btn-ghost-hover': 'rgba(255, 255, 255, 0.82)',
      '--chat-assistant-bg': 'rgba(255, 255, 255, 0.72)',
      '--chat-user-start': 'rgba(91, 95, 199, 0.92)',
      '--chat-user-end': 'rgba(0, 120, 212, 0.92)',
    },
  },
};

export const CUSTOM_FIELDS = [
  { key: 'background', label: 'Фон', var: '--color-bg' },
  { key: 'primary', label: 'Акцент', var: '--color-primary' },
  { key: 'surface', label: 'Панелі', var: '--color-surface-solid' },
  { key: 'text', label: 'Текст', var: '--color-text' },
  { key: 'textMuted', label: 'Другорядний текст', var: '--color-text-muted' },
  { key: 'accent1', label: 'Градієнт 1', var: '--gradient-spot-1' },
  { key: 'accent2', label: 'Градієнт 2', var: '--gradient-spot-2' },
];

export function hexToRgba(hex, alpha = 1) {
  if (!hex || typeof hex !== 'string') {
    return `rgba(0, 0, 0, ${alpha})`;
  }

  const normalized = hex.replace('#', '');
  if (!/^[0-9a-fA-F]{3}$|^[0-9a-fA-F]{6}$/.test(normalized)) {
    return `rgba(0, 0, 0, ${alpha})`;
  }

  const full = normalized.length === 3
    ? normalized.split('').map((c) => c + c).join('')
    : normalized;
  const num = parseInt(full, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function buildCustomVars(colors) {
  const bg = colors.background || '#EBF4F3';
  const primary = colors.primary || '#0D9E96';
  const surface = colors.surface || '#ffffff';
  const text = colors.text || '#1C3D3A';
  const textMuted = colors.textMuted || '#5E7A78';
  const accent1 = colors.accent1 || '#4ECDC4';
  const accent2 = colors.accent2 || '#A7F3F0';

  const vars = {
    ...THEME_PRESETS.light.vars,
    '--color-bg': bg,
    '--color-surface': hexToRgba(surface, 0.52),
    '--color-surface-solid': hexToRgba(surface, 0.82),
    '--color-surface-hover': hexToRgba(surface, 0.72),
    '--color-border': hexToRgba(surface, 0.65),
    '--color-border-subtle': hexToRgba(primary, 0.22),
    '--color-text': text,
    '--color-text-muted': textMuted,
    '--color-primary': primary,
    '--color-primary-hover': primary,
    '--color-primary-soft': hexToRgba(primary, 0.12),
    '--shadow': `0 8px 32px ${hexToRgba(primary, 0.12)}`,
    '--shadow-soft': `0 2px 16px ${hexToRgba(text, 0.06)}`,
    '--gradient-spot-1': hexToRgba(accent1, 0.45),
    '--gradient-spot-2': hexToRgba(accent2, 0.4),
    '--gradient-spot-3': hexToRgba(primary, 0.2),
    '--gradient-linear-start': bg,
    '--gradient-linear-mid': hexToRgba(accent1, 0.35),
    '--gradient-linear-end': hexToRgba(accent2, 0.25),
    '--input-bg': hexToRgba(surface, 0.55),
    '--input-bg-focus': hexToRgba(surface, 0.85),
    '--btn-ghost-bg': hexToRgba(surface, 0.45),
    '--btn-ghost-hover': hexToRgba(surface, 0.75),
    '--chat-assistant-bg': hexToRgba(surface, 0.62),
    '--chat-user-start': hexToRgba(primary, 0.92),
    '--chat-user-end': hexToRgba(primary, 0.88),
  };

  return {
    ...vars,
    '--body-background': buildEllipseBodyBackground(vars),
  };
}

export function applyThemeVars(vars) {
  const root = document.documentElement;
  Object.entries(vars).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
}

export function loadThemeState() {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (!raw) {
      return { type: 'preset', presetId: DEFAULT_PRESET_ID, custom: {} };
    }
    const parsed = JSON.parse(raw);
    return {
      type: parsed.type === 'custom' ? 'custom' : 'preset',
      presetId: parsed.presetId || DEFAULT_PRESET_ID,
      custom: parsed.custom || {},
    };
  } catch {
    return { type: 'preset', presetId: DEFAULT_PRESET_ID, custom: {} };
  }
}

export function resolveThemeVars(state) {
  let vars;
  if (state.type === 'custom' && Object.keys(state.custom).length > 0) {
    vars = buildCustomVars(state.custom);
  } else {
    const preset = THEME_PRESETS[state.presetId]
      || THEME_PRESETS[state.presetId === 'openai' ? 'gemini' : DEFAULT_PRESET_ID]
      || THEME_PRESETS[DEFAULT_PRESET_ID];
    vars = { ...preset.vars };
  }

  if (!vars['--body-background']) {
    vars['--body-background'] = buildEllipseBodyBackground(vars);
  }

  return vars;
}

export const DEFAULT_CUSTOM_COLORS = {
  background: '#EBF4F3',
  primary: '#0D9E96',
  surface: '#ffffff',
  text: '#1C3D3A',
  textMuted: '#5E7A78',
  accent1: '#4ECDC4',
  accent2: '#A7F3F0',
};
