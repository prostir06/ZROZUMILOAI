// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import KnowledgeGapsTable from './KnowledgeGapsTable';

const SAMPLE_GAPS = [
  {
    id: 1,
    created_at: '2026-11-18T10:00:00Z',
    sent_by: 'olena',
    channel: 'web',
    prompt: 'Web відкрите питання',
    response_snippet: 'Відповідь відсутня.',
    reason: 'low_confidence',
    is_resolved: false,
  },
  {
    id: 2,
    created_at: '2026-11-19T11:00:00Z',
    sent_by: '@ivan (@helper_bot)',
    channel: 'telegram',
    prompt: 'Telegram відкрите питання',
    response_snippet: 'Передано викладачу.',
    reason: 'low_confidence',
    is_resolved: false,
  },
  {
    id: 3,
    created_at: '2026-11-20T12:00:00Z',
    sent_by: 'Widget (edX)',
    channel: 'widget',
    prompt: 'Widget вирішене питання',
    response_snippet: 'Потрібно додати графік.',
    reason: 'negative_feedback',
    is_resolved: true,
  },
];

describe('KnowledgeGapsTable RTL channel & status filtering', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders channel filter chips with accurate counts and filters rows by channel', () => {
    render(<KnowledgeGapsTable gaps={SAMPLE_GAPS} />);

    const allChannelsBtn = screen.getByRole('button', { name: 'Усі канали (3)' });
    const webBtn = screen.getByRole('button', { name: 'Web (1)' });
    const tgBtn = screen.getByRole('button', { name: 'Telegram (1)' });
    const widgetBtn = screen.getByRole('button', { name: 'Widget (1)' });

    expect(allChannelsBtn).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Web відкрите питання')).toBeInTheDocument();
    expect(screen.getByText('Telegram відкрите питання')).toBeInTheDocument();
    expect(screen.getByText('Widget вирішене питання')).toBeInTheDocument();

    fireEvent.click(tgBtn);
    expect(tgBtn).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByText('Web відкрите питання')).not.toBeInTheDocument();
    expect(screen.getByText('Telegram відкрите питання')).toBeInTheDocument();
    expect(screen.queryByText('Widget вирішене питання')).not.toBeInTheDocument();

    fireEvent.click(webBtn);
    expect(screen.getByText('Web відкрите питання')).toBeInTheDocument();
    expect(screen.queryByText('Telegram відкрите питання')).not.toBeInTheDocument();

    fireEvent.click(widgetBtn);
    expect(screen.getByText('Widget вирішене питання')).toBeInTheDocument();
    expect(screen.queryByText('Web відкрите питання')).not.toBeInTheDocument();
  });

  it('combines status and channel filters and shows empty state when no match exists', () => {
    render(<KnowledgeGapsTable gaps={SAMPLE_GAPS} />);

    fireEvent.click(screen.getByRole('button', { name: 'Відкриті (2)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Widget (1)' }));

    expect(
      screen.getByText('Немає прогалин за обраними фільтрами.'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Вирішені (1)' }));
    expect(screen.getByText('Widget вирішене питання')).toBeInTheDocument();
  });

  it('invokes onUploadClick and onResolveClick for filtered gap rows', () => {
    const onUploadClick = vi.fn();
    const onResolveClick = vi.fn();
    render(
      <KnowledgeGapsTable
        gaps={SAMPLE_GAPS}
        onUploadClick={onUploadClick}
        onResolveClick={onResolveClick}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Telegram (1)' }));
    fireEvent.click(screen.getByRole('button', { name: /Додати матеріал/i }));
    fireEvent.click(screen.getByRole('button', { name: /Вирішено$/i }));

    expect(onUploadClick).toHaveBeenCalledWith(SAMPLE_GAPS[1]);
    expect(onResolveClick).toHaveBeenCalledWith(SAMPLE_GAPS[1], true);
  });
});
