import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '@/theme';

type Block =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'blockquote'; text: string }
  | { type: 'ul' | 'ol'; items: string[] }
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
    const trimmed = lines[index]!.trim();
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

function InlineText({ text, style }: { text: string; style?: object }) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g).filter((part) => part.length > 0);
  return (
    <Text style={style}>
      {parts.map((part, index) => {
        if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
          return (
            <Text key={`code-${index}`} style={styles.code}>
              {part.slice(1, -1)}
            </Text>
          );
        }
        if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
          return (
            <Text key={`strong-${index}`} style={styles.strong}>
              {part.slice(2, -2)}
            </Text>
          );
        }
        if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
          return (
            <Text key={`em-${index}`} style={styles.em}>
              {part.slice(1, -1)}
            </Text>
          );
        }
        return <Text key={`text-${index}`}>{part}</Text>;
      })}
    </Text>
  );
}

export function SimpleMarkdown({ markdown }: { markdown: string }) {
  const blocks = parseBlocks(markdown);
  return (
    <View style={styles.wrap}>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === 'h1' || block.type === 'h2' || block.type === 'h3') {
          return (
            <InlineText
              key={key}
              text={block.text}
              style={block.type === 'h1' ? styles.h1 : block.type === 'h2' ? styles.h2 : styles.h3}
            />
          );
        }
        if (block.type === 'blockquote') {
          return (
            <View key={key} testID="legal-blockquote" style={styles.quote} accessibilityRole="text">
              <InlineText text={block.text} style={styles.quoteText} />
            </View>
          );
        }
        if (block.type === 'table') {
          return (
            <View key={key} testID="legal-table" style={styles.table} accessibilityRole="none">
              <View style={styles.tableRow}>
                {block.headers.map((header, headerIndex) => (
                  <View key={`${key}-h-${headerIndex}`} style={styles.tableCell}>
                    <InlineText text={header} style={styles.tableHeader} />
                  </View>
                ))}
              </View>
              {block.rows.map((row, rowIndex) => (
                <View key={`${key}-r-${rowIndex}`} style={styles.tableRow}>
                  {row.map((cell, cellIndex) => (
                    <View key={`${key}-c-${rowIndex}-${cellIndex}`} style={styles.tableCell}>
                      <InlineText text={cell} style={styles.paragraph} />
                    </View>
                  ))}
                </View>
              ))}
            </View>
          );
        }
        if (block.type === 'ul' || block.type === 'ol') {
          return (
            <View key={key} style={styles.list}>
              {block.items.map((item, itemIndex) => (
                <InlineText
                  key={`${key}-${itemIndex}`}
                  text={`${block.type === 'ol' ? `${itemIndex + 1}. ` : '• '}${item}`}
                  style={styles.paragraph}
                />
              ))}
            </View>
          );
        }
        return (
          <InlineText
            key={key}
            text={block.type === 'p' ? block.text : ''}
            style={styles.paragraph}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing[2] },
  h1: { fontSize: 20, fontWeight: '700', color: colors.brandDark, marginTop: spacing[2] },
  h2: { fontSize: 17, fontWeight: '700', color: colors.text, marginTop: spacing[2] },
  h3: { fontSize: 15, fontWeight: '600', color: colors.text, marginTop: spacing[1] },
  paragraph: { color: colors.textSecondary, lineHeight: 22 },
  list: { gap: spacing[1], paddingLeft: spacing[1] },
  quote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.brandDark,
    paddingLeft: spacing[2],
    backgroundColor: colors.surfaceSubtle,
  },
  quoteText: { color: colors.text, lineHeight: 22 },
  table: { borderWidth: 1, borderColor: colors.border, borderRadius: 6, overflow: 'hidden' },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  tableCell: { flex: 1, padding: spacing[1] },
  tableHeader: { fontWeight: '700', color: colors.text, lineHeight: 20 },
  code: {
    fontFamily: 'monospace',
    backgroundColor: colors.surfaceSubtle,
    color: colors.text,
  },
  strong: { fontWeight: '700' },
  em: { fontStyle: 'italic' },
});
