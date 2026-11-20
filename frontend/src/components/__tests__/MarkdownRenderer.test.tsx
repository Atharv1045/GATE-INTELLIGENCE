import { describe, it, expect } from 'vitest';
import { renderToString } from 'react-dom/server';
import React from 'react';
import { MarkdownRenderer } from '../MarkdownRenderer';

describe('MarkdownRenderer Component', () => {
  it('renders headings 1 through 6 correctly', () => {
    const markdown = '# H1 Title\n## H2 Title\n### H3 Title\n#### H4 Title\n##### H5 Title\n###### H6 Title';
    const html = renderToString(<MarkdownRenderer content={markdown} />);
    expect(html).toContain('H1 Title');
    expect(html).toContain('H2 Title');
    expect(html).toContain('H3 Title');
    expect(html).toContain('H4 Title');
    expect(html).toContain('H5 Title');
    expect(html).toContain('H6 Title');
  });

  it('renders bold, italic, and blockquotes', () => {
    const markdown = '**Bold Concept** and *Italic Note*\n\n> This is an important GATE note';
    const html = renderToString(<MarkdownRenderer content={markdown} />);
    expect(html).toContain('Bold Concept');
    expect(html).toContain('Italic Note');
    expect(html).toContain('This is an important GATE note');
    expect(html).toContain('border-indigo-500');
  });

  it('renders ordered, unordered, and nested lists', () => {
    const markdown = '- Bullet item 1\n- Bullet item 2\n  - Nested bullet\n\n1. Numbered step 1\n2. Numbered step 2';
    const html = renderToString(<MarkdownRenderer content={markdown} />);
    expect(html).toContain('Bullet item 1');
    expect(html).toContain('Bullet item 2');
    expect(html).toContain('Nested bullet');
    expect(html).toContain('Numbered step 1');
    expect(html).toContain('Numbered step 2');
    expect(html).toContain('<ul');
    expect(html).toContain('<ol');
    expect(html).toContain('<li');
  });

  it('renders code blocks with language labels in C++, Python, and Java', () => {
    const codeMarkdown = [
      '```cpp',
      'int main() {',
      '    std::cout << "Hello GATE" << std::endl;',
      '    return 0;',
      '}',
      '```',
      '',
      '```python',
      'def dijkstra(graph, start):',
      '    distances = {node: float("inf") for node in graph}',
      '    return distances',
      '```',
      '',
      '```java',
      'class Semaphore {',
      '    private int value;',
      '}',
      '```',
    ].join('\n');

    const html = renderToString(<MarkdownRenderer content={codeMarkdown} />);
    expect(html).toContain('CPP');
    expect(html).toContain('PYTHON');
    expect(html).toContain('JAVA');
    expect(html).toContain('std::cout &lt;&lt; &quot;Hello GATE&quot;');
    expect(html).toContain('def dijkstra');
    expect(html).toContain('class Semaphore');
  });

  it('renders inline code distinctly', () => {
    const markdown = 'Use `int counter = 0;` inside the critical section.';
    const html = renderToString(<MarkdownRenderer content={markdown} />);
    expect(html).toContain('int counter = 0;');
    expect(html).toContain('text-amber-300');
  });

  it('renders GFM comparison tables with responsive wrapper', () => {
    const tableMarkdown = [
      '| Feature | Paging | Segmentation |',
      '| :--- | :--- | :--- |',
      '| Block Size | Fixed page size (e.g. 4KB) | Variable segment length |',
      '| Fragmentation | Internal fragmentation | External fragmentation |',
      '| Programmer View | Invisible to programmer | Visible logical units |',
    ].join('\n');

    const html = renderToString(<MarkdownRenderer content={tableMarkdown} />);
    expect(html).toContain('<table');
    expect(html).toContain('<thead');
    expect(html).toContain('<tbody');
    expect(html).toContain('Fixed page size (e.g. 4KB)');
    expect(html).toContain('Variable segment length');
    expect(html).toContain('Internal fragmentation');
    expect(html).toContain('External fragmentation');
  });

  it('renders inline and block LaTeX expressions using KaTeX', () => {
    const mathMarkdown = [
      'Dijkstra running time is $\\mathcal{O}((V + E) \\log V)$.',
      '',
      '$$',
      '\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}',
      '$$',
      '',
      'Matrix equation: $\\mathbf{A} \\mathbf{x} = \\mathbf{b}$ and set notation $A \\subseteq B$.',
    ].join('\n');

    const html = renderToString(<MarkdownRenderer content={mathMarkdown} />);
    expect(html).toContain('katex');
    expect(html).toContain('katex-html');
    expect(html).toContain('katex-display');
  });

  it('handles malformed LaTeX gracefully without throwing', () => {
    const malformed = 'Malformed equation: $\\frac{1}{}$ or $\\sqrt[$ or $\\text{unclosed';
    expect(() => {
      const html = renderToString(<MarkdownRenderer content={malformed} />);
      expect(html).toBeDefined();
    }).not.toThrow();
  });

  it('prevents XSS script execution by escaping raw HTML tags', () => {
    const malicious = '<script>window.pwned = true;</script><img src="x" onerror="alert(1)"/>';
    const html = renderToString(<MarkdownRenderer content={malicious} />);
    expect(html).not.toContain('<script>window.pwned');
    expect(html).not.toContain('onerror="alert(1)"');
  });

  it('renders safe external links with noopener and noreferrer', () => {
    const linkMarkdown = 'Check the [GATE CS Syllabus](https://gate2026.iitk.ac.in).';
    const html = renderToString(<MarkdownRenderer content={linkMarkdown} />);
    expect(html).toContain('href="https://gate2026.iitk.ac.in"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });
});
