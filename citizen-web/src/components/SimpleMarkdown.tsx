import type { ReactNode } from 'react';

type Block =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'blockquote'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'table'; headers: string[]; rows: string[][] };

const TABLE_SEPARATOR = /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;

function splitTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((cell) => cell.trim());
}

function isTableRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.includes('|') && splitTableRow(trimmed).length >= 2;
}

export function parseBlocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let quote: string[] = [];
  let listType: 'ul' | 'ol' | null = null;
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push({ type: 'p', text: paragraph.join(' ').trim() });
    paragraph = [];
  };

  const flushQuote = () => {
    if (!quote.length) return;
    blocks.push({ type: 'blockquote', text: quote.join(' ').trim() });
    quote = [];
  };

  const flushList = () => {
    if (!listType || !listItems.length) {
      listType = null;
      listItems = [];
      return;
    }
    blocks.push({ type: listType, items: listItems });
    listType = null;
    listItems = [];
  };

  const flushFlow = () => {
    flushParagraph();
    flushQuote();
    flushList();
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]!.trimEnd();
    const trimmed = line.trim();
    if (!trimmed) {
      flushFlow();
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushFlow();
      const level = heading[1]!.length;
      blocks.push({
        type: level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3',
        text: heading[2]!.trim(),
      });
      continue;
    }

    if (trimmed.startsWith('>')) {
      flushParagraph();
      flushList();
      quote.push(trimmed.replace(/^>\s?/, ''));
      continue;
    }

    if (isTableRow(trimmed)) {
      const next = lines[index + 1]?.trim() ?? '';
      if (TABLE_SEPARATOR.test(next)) {
        flushFlow();
        const headers = splitTableRow(trimmed);
        index += 1;
        const rows: string[][] = [];
        while (index + 1 < lines.length && isTableRow(lines[index + 1]!.trim())) {
          index += 1;
          const cells = splitTableRow(lines[index]!.trim());
          while (cells.length < headers.length) cells.push('');
          rows.push(cells.slice(0, headers.length));
        }
        blocks.push({ type: 'table', headers, rows });
        continue;
      }
    }

    const unordered = /^[-*+]\s+(.+)$/.exec(trimmed);
    if (unordered) {
      flushParagraph();
      flushQuote();
      if (listType && listType !== 'ul') flushList();
      listType = 'ul';
      listItems.push(unordered[1]!.trim());
      continue;
    }

    const ordered = /^\d+[.)]\s+(.+)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      flushQuote();
      if (listType && listType !== 'ol') flushList();
      listType = 'ol';
      listItems.push(ordered[1]!.trim());
      continue;
    }

    flushQuote();
    flushList();
    paragraph.push(trimmed);
  }

  flushFlow();
  return blocks;
}

export function inlineNodes(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g).filter((part) => part.length > 0);
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return <code key={`code-${index}`}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return <strong key={`strong-${index}`}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return <em key={`em-${index}`}>{part.slice(1, -1)}</em>;
    }
    return <span key={`text-${index}`}>{part}</span>;
  });
}

export function SimpleMarkdown({ markdown, className }: { markdown: string; className?: string }) {
  const blocks = parseBlocks(markdown);
  return (
    <div className={className ?? 'simple-markdown'} style={{ lineHeight: 1.6 }}>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === 'h1') {
          return (
            <h2
              key={key}
              style={{ marginTop: '1.25rem', marginBottom: '0.5rem', fontSize: '1.35rem' }}
            >
              {inlineNodes(block.text)}
            </h2>
          );
        }
        if (block.type === 'h2') {
          return (
            <h3
              key={key}
              style={{ marginTop: '1.1rem', marginBottom: '0.4rem', fontSize: '1.15rem' }}
            >
              {inlineNodes(block.text)}
            </h3>
          );
        }
        if (block.type === 'h3') {
          return (
            <h4
              key={key}
              style={{ marginTop: '1rem', marginBottom: '0.35rem', fontSize: '1.05rem' }}
            >
              {inlineNodes(block.text)}
            </h4>
          );
        }
        if (block.type === 'blockquote') {
          return (
            <blockquote
              key={key}
              style={{
                margin: '0.75rem 0',
                padding: '0.65rem 0.85rem',
                borderInlineStart: '3px solid #c5cdd6',
                background: '#f6f8fa',
              }}
            >
              {inlineNodes(block.text)}
            </blockquote>
          );
        }
        if (block.type === 'table') {
          return (
            <div key={key} style={{ overflowX: 'auto', margin: '0.85rem 0' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.95rem' }}>
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th
                        key={`${key}-h-${headerIndex}`}
                        style={{
                          textAlign: 'start',
                          border: '1px solid #d0d7de',
                          padding: '0.45rem 0.6rem',
                          background: '#f6f8fa',
                        }}
                      >
                        {inlineNodes(header)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`${key}-r-${rowIndex}`}>
                      {row.map((cell, cellIndex) => (
                        <td
                          key={`${key}-c-${rowIndex}-${cellIndex}`}
                          style={{
                            border: '1px solid #d0d7de',
                            padding: '0.45rem 0.6rem',
                            verticalAlign: 'top',
                          }}
                        >
                          {inlineNodes(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.type === 'ul') {
          return (
            <ul key={key} style={{ margin: '0.5rem 0', paddingInlineStart: '1.25rem' }}>
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{inlineNodes(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={key} style={{ margin: '0.5rem 0', paddingInlineStart: '1.25rem' }}>
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{inlineNodes(item)}</li>
              ))}
            </ol>
          );
        }
        return (
          <p key={key} style={{ margin: '0.65rem 0', whiteSpace: 'pre-wrap' }}>
            {inlineNodes(block.text)}
          </p>
        );
      })}
    </div>
  );
}
