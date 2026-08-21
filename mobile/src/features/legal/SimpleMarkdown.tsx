import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '@/theme';

type Block =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'ul' | 'ol'; items: string[] };

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
    const trimmed = raw.trim();
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

function plain(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1');
}

export function SimpleMarkdown({ markdown }: { markdown: string }) {
  const blocks = parseBlocks(markdown);
  return (
    <View style={styles.wrap}>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === 'h1' || block.type === 'h2' || block.type === 'h3') {
          return (
            <Text
              key={key}
              style={block.type === 'h1' ? styles.h1 : block.type === 'h2' ? styles.h2 : styles.h3}
            >
              {plain(block.text)}
            </Text>
          );
        }
        if (block.type === 'ul' || block.type === 'ol') {
          return (
            <View key={key} style={styles.list}>
              {block.items.map((item, i) => (
                <Text key={`${key}-${i}`} style={styles.paragraph}>
                  {block.type === 'ol' ? `${i + 1}. ` : '• '}
                  {plain(item)}
                </Text>
              ))}
            </View>
          );
        }
        return (
          <Text key={key} style={styles.paragraph}>
            {plain(block.type === 'p' ? block.text : '')}
          </Text>
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
});
