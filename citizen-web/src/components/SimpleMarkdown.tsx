import type { ReactNode } from 'react';

type Block =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] };

function parseBlocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let listType: 'ul' | 'ol' | null = null;
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push({ type: 'p', text: paragraph.join(' ').trim() });
    paragraph = [];
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

  for (const raw of lines) {
    const line = raw.trimEnd();
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1]!.length;
      blocks.push({
        type: level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3',
        text: heading[2]!.trim(),
      });
      continue;
    }

    const unordered = /^[-*+]\s+(.+)$/.exec(trimmed);
    if (unordered) {
      flushParagraph();
      if (listType && listType !== 'ul') flushList();
      listType = 'ul';
      listItems.push(unordered[1]!.trim());
      continue;
    }

    const ordered = /^\d+[.)]\s+(.+)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      if (listType && listType !== 'ol') flushList();
      listType = 'ol';
      listItems.push(ordered[1]!.trim());
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function inlineText(text: string): ReactNode {
  // Keep markup literal — no HTML injection. Strip bare emphasis markers lightly.
  return text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1');
}

export function SimpleMarkdown({ markdown, className }: { markdown: string; className?: string }) {
  const blocks = parseBlocks(markdown);
  return (
    <div className={className ?? 'simple-markdown'} style={{ lineHeight: 1.6 }}>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === 'h1') {
          return (
            <h2 key={key} style={{ marginTop: '1.25rem', marginBottom: '0.5rem', fontSize: '1.35rem' }}>
              {inlineText(block.text)}
            </h2>
          );
        }
        if (block.type === 'h2') {
          return (
            <h3 key={key} style={{ marginTop: '1.1rem', marginBottom: '0.4rem', fontSize: '1.15rem' }}>
              {inlineText(block.text)}
            </h3>
          );
        }
        if (block.type === 'h3') {
          return (
            <h4 key={key} style={{ marginTop: '1rem', marginBottom: '0.35rem', fontSize: '1.05rem' }}>
              {inlineText(block.text)}
            </h4>
          );
        }
        if (block.type === 'ul') {
          return (
            <ul key={key} style={{ margin: '0.5rem 0', paddingInlineStart: '1.25rem' }}>
              {block.items.map((item, i) => (
                <li key={`${key}-${i}`}>{inlineText(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={key} style={{ margin: '0.5rem 0', paddingInlineStart: '1.25rem' }}>
              {block.items.map((item, i) => (
                <li key={`${key}-${i}`}>{inlineText(item)}</li>
              ))}
            </ol>
          );
        }
        return (
          <p key={key} style={{ margin: '0.65rem 0', whiteSpace: 'pre-wrap' }}>
            {inlineText(block.text)}
          </p>
        );
      })}
    </div>
  );
}
