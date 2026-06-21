import { describe, expect, it } from 'vitest';

import {
  DEFAULT_PRESET_ID,
  hexToRgba,
  resolveThemeVars,
  THEME_PRESETS,
} from '../themes/presets.js';

describe('hexToRgba', () => {
  it('конвертує 6-символьний hex', () => {
    expect(hexToRgba('#0D9E96', 0.5)).toBe('rgba(13, 158, 150, 0.5)');
  });

  it('конвертує 3-символьний hex', () => {
    expect(hexToRgba('#fff')).toBe('rgba(255, 255, 255, 1)');
  });

  it('повертає fallback для невалідного hex', () => {
    expect(hexToRgba('invalid')).toBe('rgba(0, 0, 0, 1)');
    expect(hexToRgba(null)).toBe('rgba(0, 0, 0, 1)');
  });
});

describe('resolveThemeVars', () => {
  it('повертає preset за замовчуванням', () => {
    const vars = resolveThemeVars({ type: 'preset', presetId: DEFAULT_PRESET_ID });
    expect(vars['--color-primary']).toBe(THEME_PRESETS.light.vars['--color-primary']);
  });

  it('мапить legacy openai на gemini', () => {
    const vars = resolveThemeVars({ type: 'preset', presetId: 'openai' });
    expect(vars['--color-primary']).toBe(THEME_PRESETS.gemini.vars['--color-primary']);
  });
});
