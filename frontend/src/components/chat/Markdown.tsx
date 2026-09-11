/**
 * Minimal, dependency-free, XSS-safe Markdown renderer for chat answers
 * (AC-4.1.3 "markdown rendering").
 *
 * Supported: paragraphs, line breaks, unordered/ordered lists, bold (**),
 * italic (*), and inline code (`code`). Rendered as React elements — never
 * via dangerouslySetInnerHTML — so no untrusted HTML can be injected.
 */

import { Fragment, type ReactNode } from "react";

/** Parse a single line's inline formatting into React nodes. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Tokenize on **bold**, *italic*, and `code` while keeping plain text.
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  const parts = text.split(pattern).filter((p) => p !== "");

  parts.forEach((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      nodes.push(<strong key={key}>{part.slice(2, -2)}</strong>);
    } else if (part.startsWith("*") && part.endsWith("*")) {
      nodes.push(<em key={key}>{part.slice(1, -1)}</em>);
    } else if (part.startsWith("`") && part.endsWith("`")) {
      nodes.push(
        <code key={key} className="rounded bg-black/10 px-1 py-0.5 text-[0.85em]">
          {part.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(<Fragment key={key}>{part}</Fragment>);
    }
  });

  return nodes;
}

export default function Markdown({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];

  let listItems: { ordered: boolean; text: string }[] = [];

  const flushList = (key: string) => {
    if (listItems.length === 0) return;
    const ordered = listItems[0].ordered;
    const items = listItems.map((li, i) => (
      <li key={`${key}-li-${i}`}>{renderInline(li.text, `${key}-li-${i}`)}</li>
    ));
    blocks.push(
      ordered ? (
        <ol key={key} className="my-1 list-inside list-decimal space-y-0.5">
          {items}
        </ol>
      ) : (
        <ul key={key} className="my-1 list-inside list-disc space-y-0.5">
          {items}
        </ul>
      ),
    );
    listItems = [];
  };

  lines.forEach((line, idx) => {
    const key = `b-${idx}`;
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);

    if (bullet) {
      listItems.push({ ordered: false, text: bullet[1] });
      return;
    }
    if (ordered) {
      listItems.push({ ordered: true, text: ordered[1] });
      return;
    }

    // Non-list line: flush any pending list first.
    flushList(`list-${idx}`);

    if (line.trim() === "") return; // collapse blank lines
    blocks.push(
      <p key={key} className="whitespace-pre-wrap break-words">
        {renderInline(line, key)}
      </p>,
    );
  });

  flushList("list-end");

  return <div className="space-y-1">{blocks}</div>;
}
