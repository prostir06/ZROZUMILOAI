// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TelegramBotFormModal from './TelegramBotFormModal';

const SAMPLE_WORKSPACES = [
  { id: 1, name: 'Курс лідерства' },
];

const SAMPLE_FORM = {
  name: 'Тестовий бот',
  token: '123456:ABCDEF',
  workspace: '1',
  is_active: true,
};

describe('TelegramBotFormModal', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('calls onSubmit when form is submitted', async () => {
    const onSubmit = vi.fn().mockResolvedValue({});
    const { container } = render(
      <TelegramBotFormModal
        formMode="create"
        form={SAMPLE_FORM}
        workspaces={SAMPLE_WORKSPACES}
        saving={false}
        onClose={vi.fn()}
        onChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const form = container.querySelector('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
  });

  it('logs error via console.error when onSubmit rejects unexpectedly', async () => {
    const rejection = new Error('Unexpected submit crash');
    const onSubmit = vi.fn().mockRejectedValue(rejection);
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <TelegramBotFormModal
        formMode="edit"
        form={SAMPLE_FORM}
        workspaces={SAMPLE_WORKSPACES}
        saving={false}
        onClose={vi.fn()}
        onChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.submit(screen.getByRole('button', { name: 'Зберегти' }).closest('form'));

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to submit telegram bot form:',
        rejection,
      );
    });
  });
});
