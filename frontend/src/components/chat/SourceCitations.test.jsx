import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import SourceCitations from './SourceCitations';

describe('SourceCitations', () => {
  it('renders citation badges with document name and score', () => {
    const sources = [
      { document_name: 'syllabus.pdf', score: 0.85, content: 'Course intro' },
    ];
    const html = renderToString(<SourceCitations sources={sources} />);
    expect(html).toContain('syllabus.pdf');
    expect(html).toContain('85%');
  });

  it('renders nothing when sources empty or missing', () => {
    expect(renderToString(<SourceCitations sources={[]} />)).toBe('');
    expect(renderToString(<SourceCitations sources={null} />)).toBe('');
    expect(renderToString(<SourceCitations sources={undefined} />)).toBe('');
    expect(renderToString(<SourceCitations />)).toBe('');
  });

  it('formats score correctly for decimal and percentage scores', () => {
    const sources = [
      { document_name: 'doc1.pdf', score: 0.923, content: 'Some snippet' },
      { document_name: 'doc2.pdf', score: 78, content: 'Another snippet' },
      { document_name: 'doc3.pdf', score: null, content: 'No score snippet' },
    ];
    const html = renderToString(<SourceCitations sources={sources} />);
    expect(html).toContain('doc1.pdf');
    expect(html).toContain('92%');
    expect(html).toContain('doc2.pdf');
    expect(html).toContain('78%');
    expect(html).toContain('doc3.pdf');
  });

  it('renders expandable citation snippet content', () => {
    const sources = [
      { document_name: 'guide.docx', score: 0.65, content: 'Step 1: Open settings' },
    ];
    const html = renderToString(<SourceCitations sources={sources} />);
    expect(html).toContain('guide.docx');
    expect(html).toContain('Step 1: Open settings');
  });

  it('handles fallback when document_name is missing', () => {
    const sources = [
      { score: 0.8, content: 'Anonymous content' },
    ];
    const html = renderToString(<SourceCitations sources={sources} />);
    expect(html).toContain('80%');
    expect(html).toContain('Джерело');
  });
});
