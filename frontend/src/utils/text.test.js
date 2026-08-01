import { describe, expect, it } from 'vitest';
import { truncateText } from './text.js';

describe('truncateText', () => {
  it('скорочує довгий текст', () => {
    expect(truncateText('abcdefgh', 5)).toBe('abcde…');
  });

  it('порожній текст → em dash', () => {
    expect(truncateText('', 10)).toBe('—');
  });
});
