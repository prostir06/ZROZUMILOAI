// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import TimelineChart from './TimelineChart';

const SAMPLE_TIMELINE = [
  {
    date: '2026-11-19',
    total_queries: 5,
    handoffs: 1,
    web: 2,
    telegram: 2,
    widget: 1,
  },
  {
    date: '2026-11-20',
    total_queries: 4,
    handoffs: 0,
    web: 1,
    telegram: 0,
    widget: 3,
  },
];

describe('TimelineChart component', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders empty state when timeline is empty', () => {
    render(<TimelineChart timeline={[]} />);

    expect(
      screen.getByText('Немає даних для відображення динаміки за обраний період.'),
    ).toBeInTheDocument();
  });

  it('renders stacked channel bars, legend totals, and handoff marker', () => {
    const { container } = render(<TimelineChart timeline={SAMPLE_TIMELINE} />);

    expect(screen.getByText('Динаміка запитів за каналами')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Web/i })).toHaveTextContent('3');
    expect(screen.getByRole('button', { name: /Telegram/i })).toHaveTextContent('2');
    expect(screen.getByRole('button', { name: /Widget/i })).toHaveTextContent('4');

    expect(container.querySelectorAll('[data-channel="web"]')).toHaveLength(2);
    expect(container.querySelectorAll('[data-channel="telegram"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-channel="widget"]')).toHaveLength(2);
    expect(container.querySelectorAll('.timeline-chart__handoff-dot')).toHaveLength(1);
    expect(screen.getByText('19.11')).toBeInTheDocument();
    expect(screen.getByText('20.11')).toBeInTheDocument();
  });

  it('toggles channel visibility and shows hint when all channels are disabled', () => {
    const { container } = render(<TimelineChart timeline={SAMPLE_TIMELINE} />);

    const tgToggle = screen.getByRole('button', { name: /Telegram/i });
    expect(tgToggle).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(tgToggle);
    expect(tgToggle).toHaveAttribute('aria-pressed', 'false');
    expect(container.querySelectorAll('[data-channel="telegram"]')).toHaveLength(0);
    expect(container.querySelectorAll('[data-channel="web"]')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: /Web/i }));
    fireEvent.click(screen.getByRole('button', { name: /Widget/i }));

    expect(
      screen.getByText('Увімкніть хоча б один канал для відображення графіка.'),
    ).toBeInTheDocument();
  });

  it('shows per-channel day details on hover or keyboard focus', () => {
    render(<TimelineChart timeline={SAMPLE_TIMELINE} />);

    expect(
      screen.getByText('Наведіть або оберіть день на графіку для деталізації за каналами.'),
    ).toBeInTheDocument();

    const dayGroup = screen.getByTestId('timeline-day-2026-11-19');
    fireEvent.mouseEnter(dayGroup);

    const detail = document.querySelector('.timeline-chart__detail');
    expect(detail).toHaveTextContent('2026-11-19');
    expect(detail).toHaveTextContent('Всього: 5');
    expect(detail).toHaveTextContent('Web: 2');
    expect(detail).toHaveTextContent('Telegram: 2');
    expect(detail).toHaveTextContent('Widget: 1');
    expect(detail).toHaveTextContent('Handoff: 1');

    fireEvent.mouseLeave(dayGroup);
    fireEvent.focus(screen.getByTestId('timeline-day-2026-11-20'));
    expect(detail).toHaveTextContent('2026-11-20');
    expect(detail).toHaveTextContent('Всього: 4');
    expect(detail).toHaveTextContent('Widget: 3');
  });

  it('falls back to web count for legacy timeline points without channel keys', () => {
    const { container } = render(
      <TimelineChart
        timeline={[{ date: '2026-11-18', total_queries: 6, handoffs: 0 }]}
      />,
    );

    expect(container.querySelectorAll('[data-channel="web"]')).toHaveLength(1);
    expect(screen.getByRole('button', { name: /Web/i })).toHaveTextContent('6');
    expect(screen.getByRole('button', { name: /Telegram/i })).toHaveTextContent('0');
    expect(screen.getByRole('button', { name: /Widget/i })).toHaveTextContent('0');
  });
});
