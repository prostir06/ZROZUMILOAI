import { useMemo, useState } from 'react';

export const TIMELINE_CHANNELS = [
  {
    id: 'web',
    label: 'Web',
    className: 'timeline-chart__bar--web',
    swatchClass: 'timeline-chart__swatch--web',
  },
  {
    id: 'telegram',
    label: 'Telegram',
    className: 'timeline-chart__bar--telegram',
    swatchClass: 'timeline-chart__swatch--telegram',
  },
  {
    id: 'widget',
    label: 'Widget',
    className: 'timeline-chart__bar--widget',
    swatchClass: 'timeline-chart__swatch--widget',
  },
];

const SVG_WIDTH = 720;
const SVG_HEIGHT = 240;
const CHART_MARGIN = { top: 20, right: 16, bottom: 32, left: 44 };
const PLOT_WIDTH = SVG_WIDTH - CHART_MARGIN.left - CHART_MARGIN.right;
const PLOT_HEIGHT = SVG_HEIGHT - CHART_MARGIN.top - CHART_MARGIN.bottom;
const BASELINE_Y = CHART_MARGIN.top + PLOT_HEIGHT;

export function formatShortDate(isoDate) {
  if (!isoDate || typeof isoDate !== 'string') return '';
  const parts = isoDate.split('-');
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}.${parts[1]}`;
}

export function normalizeTimelinePoint(point) {
  const total = Number(point?.total_queries ?? 0);
  const safeTotal = Number.isFinite(total) ? total : 0;
  const handoffs = Number(point?.handoffs ?? 0);
  const safeHandoffs = Number.isFinite(handoffs) ? handoffs : 0;
  const hasBreakdown =
    point?.web !== undefined
    || point?.telegram !== undefined
    || point?.widget !== undefined;

  const web = hasBreakdown ? Number(point?.web ?? 0) : safeTotal;
  const telegram = hasBreakdown ? Number(point?.telegram ?? 0) : 0;
  const widget = hasBreakdown ? Number(point?.widget ?? 0) : 0;

  return {
    date: String(point?.date || ''),
    total_queries: safeTotal,
    handoffs: safeHandoffs,
    web: Number.isFinite(web) ? web : 0,
    telegram: Number.isFinite(telegram) ? telegram : 0,
    widget: Number.isFinite(widget) ? widget : 0,
  };
}

function buildYTicks(maxVal) {
  if (maxVal <= 4) {
    const ticks = [];
    for (let val = 0; val <= maxVal; val += 1) {
      ticks.push(val);
    }
    return ticks;
  }
  const step = Math.ceil(maxVal / 4);
  return [0, step, step * 2, step * 3, step * 4];
}

function shouldRenderXLabel(index, totalPoints, labelStep) {
  if (totalPoints <= 1) return true;
  if (index === 0 || index === totalPoints - 1) return true;
  if (index % labelStep !== 0) return false;
  return totalPoints - 1 - index >= Math.ceil(labelStep / 2);
}

/**
 * Stacked timeline chart displaying daily query dynamics across Web, Telegram, and Widget channels.
 *
 * @param {Object} props
 * @param {Array<Object>} [props.timeline=[]] - Daily timeline points returned by workspace analytics API.
 * @param {boolean} [props.isLoading=false] - Loading indicator state.
 */
export default function TimelineChart({ timeline = [], isLoading = false }) {
  const [visibleChannels, setVisibleChannels] = useState({
    web: true,
    telegram: true,
    widget: true,
  });
  const [activeIndex, setActiveIndex] = useState(null);

  const points = useMemo(
    () => (
      Array.isArray(timeline)
        ? timeline
            .filter((item) => item && typeof item === 'object')
            .map(normalizeTimelinePoint)
        : []
    ),
    [timeline],
  );

  const channelTotals = useMemo(
    () => points.reduce(
      (acc, point) => ({
        web: acc.web + point.web,
        telegram: acc.telegram + point.telegram,
        widget: acc.widget + point.widget,
      }),
      { web: 0, telegram: 0, widget: 0 },
    ),
    [points],
  );

  const activeChannels = useMemo(
    () => TIMELINE_CHANNELS.filter((ch) => visibleChannels[ch.id]),
    [visibleChannels],
  );

  const getVisibleTotal = (point) => activeChannels.reduce(
    (sum, ch) => sum + point[ch.id],
    0,
  );

  const hasHandoffs = points.some((point) => point.handoffs > 0);
  const maxVisibleVal = Math.max(1, ...points.map(getVisibleTotal));
  const yTicks = buildYTicks(maxVisibleVal);
  const yMax = yTicks[yTicks.length - 1] || 1;
  const labelStep = points.length > 0 ? Math.max(1, Math.ceil(points.length / 10)) : 1;

  const activePoint = activeIndex !== null && points[activeIndex] ? points[activeIndex] : null;

  const toggleChannel = (channelId) => {
    setVisibleChannels((prev) => ({
      ...prev,
      [channelId]: !prev[channelId],
    }));
  };

  return (
    <section
      className={`timeline-chart ${isLoading ? 'timeline-chart--loading' : ''}`}
      aria-label="Динаміка запитів за каналами"
    >
      <div className="timeline-chart__header">
        <div>
          <h5 className="timeline-chart__title">Динаміка запитів за каналами</h5>
          <p className="timeline-chart__subtitle">
            Щоденна активність у розрізі Web, Telegram та Widget
          </p>
        </div>

        <div className="timeline-chart__legend" role="group" aria-label="Фільтр каналів графіка">
          {TIMELINE_CHANNELS.map((ch) => {
            const pressed = Boolean(visibleChannels[ch.id]);
            return (
              <button
                key={ch.id}
                type="button"
                className={`timeline-chart__toggle ${
                  pressed ? 'timeline-chart__toggle--active' : 'timeline-chart__toggle--muted'
                }`}
                aria-pressed={pressed}
                onClick={() => toggleChannel(ch.id)}
              >
                <span className={`timeline-chart__swatch ${ch.swatchClass}`} aria-hidden="true" />
                <span>{ch.label}</span>
                <span className="timeline-chart__toggle-count">{channelTotals[ch.id]}</span>
              </button>
            );
          })}
          {hasHandoffs && (
            <span className="timeline-chart__handoff-legend" title="Дні з передачею викладачу">
              <span className="timeline-chart__swatch timeline-chart__swatch--handoff" aria-hidden="true" />
              <span>Handoff</span>
            </span>
          )}
        </div>
      </div>

      {points.length === 0 ? (
        <p className="empty-state timeline-chart__empty">
          Немає даних для відображення динаміки за обраний період.
        </p>
      ) : activeChannels.length === 0 ? (
        <p className="empty-state timeline-chart__empty">
          Увімкніть хоча б один канал для відображення графіка.
        </p>
      ) : (
        <>
          <div className="timeline-chart__canvas-wrap">
            <svg
              className="timeline-chart__svg"
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
              role="img"
              aria-label="Графік динаміки запитів за каналами Web, Telegram та Widget"
            >
              {yTicks.map((tick) => {
                const y = BASELINE_Y - (tick / yMax) * PLOT_HEIGHT;
                return (
                  <g key={tick} className="timeline-chart__grid-row">
                    <line
                      x1={CHART_MARGIN.left}
                      x2={SVG_WIDTH - CHART_MARGIN.right}
                      y1={y}
                      y2={y}
                      className={tick === 0 ? 'timeline-chart__axis' : 'timeline-chart__gridline'}
                    />
                    <text
                      x={CHART_MARGIN.left - 8}
                      y={y + 4}
                      textAnchor="end"
                      className="timeline-chart__axis-label"
                    >
                      {tick}
                    </text>
                  </g>
                );
              })}

              {points.map((point, idx) => {
                const slotWidth = PLOT_WIDTH / points.length;
                const barWidth = Math.min(36, Math.max(8, slotWidth * 0.6));
                const slotX = CHART_MARGIN.left + idx * slotWidth;
                const barX = slotX + (slotWidth - barWidth) / 2;
                const barCenterX = barX + barWidth / 2;
                const isSelected = activeIndex === idx;

                let currentBottomY = BASELINE_Y;
                const segments = [];
                activeChannels.forEach((ch) => {
                  const val = point[ch.id];
                  if (val <= 0) return;
                  const availableHeight = currentBottomY - CHART_MARGIN.top;
                  const rawHeight = (val / yMax) * PLOT_HEIGHT;
                  const segHeight = Math.min(Math.max(2, rawHeight), availableHeight);
                  if (segHeight <= 0) return;
                  const segY = currentBottomY - segHeight;
                  segments.push({
                    channelId: ch.id,
                    className: ch.className,
                    x: barX,
                    y: segY,
                    width: barWidth,
                    height: segHeight,
                    value: val,
                  });
                  currentBottomY = segY;
                });

                const summaryText = `${point.date}: Web ${point.web}, Telegram ${point.telegram}, Widget ${point.widget}${
                  point.handoffs > 0 ? `, Handoff ${point.handoffs}` : ''
                }`;

                return (
                  <g
                    key={point.date || idx}
                    className={`timeline-chart__day ${isSelected ? 'timeline-chart__day--active' : ''}`}
                    data-testid={`timeline-day-${point.date}`}
                    tabIndex={0}
                    role="group"
                    aria-label={summaryText}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onMouseLeave={() => setActiveIndex(null)}
                    onFocus={() => setActiveIndex(idx)}
                    onBlur={() => setActiveIndex(null)}
                  >
                    <title>{summaryText}</title>
                    <rect
                      x={slotX}
                      y={CHART_MARGIN.top}
                      width={slotWidth}
                      height={PLOT_HEIGHT}
                      fill="transparent"
                    />
                    {segments.map((seg) => (
                      <rect
                        key={seg.channelId}
                        className={`timeline-chart__bar ${seg.className}`}
                        data-channel={seg.channelId}
                        data-date={point.date}
                        x={seg.x}
                        y={seg.y}
                        width={seg.width}
                        height={seg.height}
                        rx={1.5}
                      />
                    ))}
                    {point.handoffs > 0 && (
                      <circle
                        className="timeline-chart__handoff-dot"
                        cx={barCenterX}
                        cy={Math.max(CHART_MARGIN.top - 6, currentBottomY - 7)}
                        r={3.5}
                      />
                    )}
                    {shouldRenderXLabel(idx, points.length, labelStep) && (
                      <text
                        x={barCenterX}
                        y={BASELINE_Y + 18}
                        textAnchor="middle"
                        className="timeline-chart__axis-label"
                      >
                        {formatShortDate(point.date)}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>

          <div className="timeline-chart__detail" aria-live="polite">
            {activePoint ? (
              <div className="timeline-chart__detail-row">
                <strong className="timeline-chart__detail-date">{activePoint.date}</strong>
                <span className="timeline-chart__detail-total">
                  Всього: <strong>{getVisibleTotal(activePoint)}</strong>
                </span>
                <span className="badge badge--web">{`Web: ${activePoint.web}`}</span>
                <span className="badge badge--telegram">{`Telegram: ${activePoint.telegram}`}</span>
                <span className="badge badge--widget">{`Widget: ${activePoint.widget}`}</span>
                {activePoint.handoffs > 0 && (
                  <span className="timeline-chart__detail-handoff">
                    {`Handoff: ${activePoint.handoffs}`}
                  </span>
                )}
              </div>
            ) : (
              <span className="timeline-chart__detail-hint">
                Наведіть або оберіть день на графіку для деталізації за каналами.
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
