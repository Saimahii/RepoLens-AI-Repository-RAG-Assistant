import { useState } from 'react';

// CodeBlock renders fenced code inside Markdown answers safely (no dangerouslySetInnerHTML)
export default function CodeBlock({ code, language, file, lines }) {
  const [copied, setCopied] = useState(false);

  const text = typeof code === 'string' ? code : code?.content || '';
  const headerLabel = file
    ? `${file}${lines ? ` (lines ${lines})` : ''}`
    : language || 'code';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may be unavailable in restricted contexts
    }
  };

  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-file">{headerLabel}</span>
        <button type="button" className="code-copy" onClick={handleCopy}>
          {copied ? '✓ copied' : 'copy'}
        </button>
      </div>
      <pre className="code-pre">
        <code>{text}</code>
      </pre>
    </div>
  );
}
