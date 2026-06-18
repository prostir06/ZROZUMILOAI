import { useTheme } from '../context/ThemeContext';
import { CUSTOM_FIELDS, DEFAULT_CUSTOM_COLORS } from '../themes/presets';

function AppearancePage() {
  const {
    presets,
    customColors,
    setPreset,
    setCustomColor,
    resetTheme,
    isCustom,
    activePresetId,
  } = useTheme();

  const handleCustomChange = (key, value) => {
    setCustomColor(key, value);
  };

  return (
    <div className="page">
      <header className="page__header page__header--row">
        <div>
          <h2>Оформлення</h2>
          <p>Оберіть шаблон або налаштуйте кольори самостійно</p>
        </div>
        <button type="button" className="btn btn--ghost" onClick={resetTheme}>
          Скинути
        </button>
      </header>

      <section className="section">
        <h3 className="section__title">Готові шаблони</h3>
        <div className="theme-grid">
          {presets.map((preset) => {
            const isActive = !isCustom && activePresetId === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                className={`theme-card ${isActive ? 'theme-card--active' : ''}`}
                onClick={() => setPreset(preset.id)}
                aria-pressed={isActive}
              >
                <div className="theme-card__preview">
                  {preset.preview.map((color) => (
                    <span
                      key={color}
                      className="theme-card__swatch"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
                <span className="theme-card__name">{preset.name}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="section card">
        <h3 className="section__title">Власні кольори</h3>
        <p className="theme-custom-hint">
          Змініть будь-який колір — тема перемкнеться в режим налаштування
        </p>
        <div className="theme-custom-grid">
          {CUSTOM_FIELDS.map((field) => (
            <div key={field.key} className="theme-custom-field">
              <label htmlFor={`color-${field.key}`}>{field.label}</label>
              <div className="theme-custom-input">
                <input
                  id={`color-${field.key}`}
                  type="color"
                  value={customColors[field.key] || DEFAULT_CUSTOM_COLORS[field.key]}
                  onChange={(e) => handleCustomChange(field.key, e.target.value)}
                />
                <span className="theme-custom-value">
                  {customColors[field.key] || DEFAULT_CUSTOM_COLORS[field.key]}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default AppearancePage;
