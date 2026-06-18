import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  DEFAULT_CUSTOM_COLORS,
  DEFAULT_PRESET_ID,
  THEME_PRESETS,
  THEME_STORAGE_KEY,
  applyThemeVars,
  loadThemeState,
  resolveThemeVars,
} from '../themes/presets';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [themeState, setThemeState] = useState(loadThemeState);

  const applyState = useCallback((state) => {
    applyThemeVars(resolveThemeVars(state));
  }, []);

  useEffect(() => {
    applyState(themeState);
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(themeState));
  }, [themeState, applyState]);

  const setPreset = useCallback((presetId) => {
    setThemeState({ type: 'preset', presetId, custom: {} });
  }, []);

  const setCustomColor = useCallback((key, value) => {
    setThemeState((prev) => ({
      type: 'custom',
      presetId: prev.presetId,
      custom: {
        ...(prev.custom || DEFAULT_CUSTOM_COLORS),
        [key]: value,
      },
    }));
  }, []);

  const setCustomColors = useCallback((colors) => {
    setThemeState({
      type: 'custom',
      presetId: 'custom',
      custom: colors,
    });
  }, []);

  const resetTheme = useCallback(() => {
    setThemeState({ type: 'preset', presetId: DEFAULT_PRESET_ID, custom: {} });
  }, []);

  const value = useMemo(() => ({
    themeState,
    presets: Object.values(THEME_PRESETS),
    customColors: { ...DEFAULT_CUSTOM_COLORS, ...themeState.custom },
    setPreset,
    setCustomColor,
    setCustomColors,
    resetTheme,
    isCustom: themeState.type === 'custom',
    activePresetId: themeState.type === 'preset' ? themeState.presetId : null,
  }), [themeState, setPreset, setCustomColor, setCustomColors, resetTheme]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
