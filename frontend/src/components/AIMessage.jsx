import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '../styles/ChatThread.css';
import CodeBlock from './CodeBlock';
import { IFile, ICopy, IRefresh, ICode, IBug, ILayers } from '../utils/icons';

const AGENT_LABELS = {
  explainer: 'Code Explainer',
  debugger: 'Debugger',
  bugfinder: 'Bug Finder',
  architect: 'Architecture Explainer',
};

const AGENT_ICONS = {
  explainer: ICode,
  debugger: IBug,
  bugfinder: IBug,
  architect: ILayers,
};

// Clickable chip showing a grounded source file + line range
function SourceChip({ source, onClick }) {
  const lineRange =
    source.start_line && source.end_line
      ? `${source.start_line}-${source.end_line}`
      : source.start_line
      ? `${source.start_line}`
      : '';

  return (
    <button
      type="button"
      className="source-chip"
      onClick={() => onClick && onClick(source)}
      title={`Open ${source.file_path}${lineRange ? ` (lines ${lineRange})` : ''} in Monaco Editor`}
    >
      <IFile />
      <span>{source.file_path}</span>
      {lineRange && <span className="source-chip-lines">:{lineRange}</span>}
    </button>
  );
}

// Full AI response card — agent badge, clickable sources, safe Markdown body, actions
export default function AIMessage({ msg, showSources, onOpenSource, onRewrite }) {
  const [copied, setCopied] = useState(false);

  const agentKey = msg.agent || 'explainer';
  const AgentIcon = AGENT_ICONS[agentKey] || ICode;
  const agentLabel = AGENT_LABELS[agentKey] || 'Code Explainer';
  const markdownText = typeof msg.content === 'string' ? msg.content : '';

  const handleCopyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(markdownText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignore if clipboard access is blocked
    }
  };

  return (
    <div className="msg-ai">
      {/* Agent badge — shows which backend agent answered */}
      <div className="msg-ai-header">
        <span className={`agent-badge ${agentKey}`}>
          <AgentIcon /> {agentLabel}
        </span>
      </div>

      {/* Grounded source file chips — clicking opens Monaco at the exact line range */}
      {showSources && msg.sources?.length > 0 && (
        <div>
          <div className="sources-label">SOURCES (click to view in editor)</div>
          <div className="sources-row">
            {msg.sources.map((src, i) => (
              <SourceChip
                key={`${src.file_path}-${src.start_line}-${src.end_line}-${i}`}
                source={src}
                onClick={onOpenSource}
              />
            ))}
          </div>
        </div>
      )}

      {/* Markdown answer rendered safely via react-markdown */}
      <div className="msg-ai-body markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ className, children, ...props }) {
              const match = /language-([\w-]+)/.exec(className || '');
              const raw = String(children).replace(/\n$/, '');
              const isBlock = Boolean(match) || raw.includes('\n');
              if (isBlock) {
                return <CodeBlock code={raw} language={match ? match[1] : ''} />;
              }
              return (
                <code className="inline-code" {...props}>
                  {children}
                </code>
              );
            },
            // Avoid wrapping our CodeBlock div inside a duplicate <pre>
            pre({ children }) {
              return <>{children}</>;
            },
          }}
        >
          {markdownText}
        </ReactMarkdown>
      </div>

      {/* Action buttons */}
      <div className="msg-actions">
        <button type="button" className="msg-action-btn" onClick={handleCopyAnswer}>
          <ICopy /> {copied ? 'Copied' : 'Copy'}
        </button>
        {onRewrite && (
          <button type="button" className="msg-action-btn" onClick={() => onRewrite(msg)}>
            <IRefresh /> Rewrite
          </button>
        )}
      </div>
    </div>
  );
}
