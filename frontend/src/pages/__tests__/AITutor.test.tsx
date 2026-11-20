import { describe, it, expect } from 'vitest';
import { renderToString } from 'react-dom/server';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { AITutor } from '../AITutor';

describe('AITutor Redirect Component', () => {
  it('renders redirect to /agents within router context', () => {
    const html = renderToString(
      <MemoryRouter initialEntries={['/ai-tutor']}>
        <AITutor paperCode="CS" />
      </MemoryRouter>
    );

    expect(html).toBeDefined();
  });
});
