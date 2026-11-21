import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_PRESET_ID,
  hexToRgba,
  loadThemeState,
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

  it('мапить збережені presetId openai і gemini на blue', () => {
    const fromOpenAI = resolveThemeVars({ type: 'preset', presetId: 'openai' });
    const fromGemini = resolveThemeVars({ type: 'preset', presetId: 'gemini' });
    expect(fromOpenAI['--color-primary']).toBe(THEME_PRESETS.blue.vars['--color-primary']);
    expect(fromGemini['--color-primary']).toBe(THEME_PRESETS.blue.vars['--color-primary']);
    expect(THEME_PRESETS.blue.name).not.toMatch(/gemini/i);
  });
});

describe('loadThemeState', () => {
  const originalLocalStorage = globalThis.localStorage;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    if (originalLocalStorage === undefined) {
      delete globalThis.localStorage;
    } else {
      globalThis.localStorage = originalLocalStorage;
    }
    vi.restoreAllMocks();
  });

  it('logs warning and returns default state on corrupted JSON', () => {
    globalThis.localStorage = {
      getItem: vi.fn().mockReturnValue('{bad json'),
    };
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const state = loadThemeState();

    expect(state).toEqual({
      type: 'preset',
      presetId: DEFAULT_PRESET_ID,
      custom: {},
    });
    expect(warnSpy).toHaveBeenCalledWith(
      'Failed to load theme state from localStorage:',
      expect.any(Error),
    );
  });

  it('logs warning and returns default state when localStorage throws', () => {
    globalThis.localStorage = {
      getItem: vi.fn(() => {
        throw new Error('SecurityError');
      }),
    };
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const state = loadThemeState();

    expect(state).toEqual({
      type: 'preset',
      presetId: DEFAULT_PRESET_ID,
      custom: {},
    });
    expect(warnSpy).toHaveBeenCalledWith(
      'Failed to load theme state from localStorage:',
      expect.any(Error),
    );
  });
});
