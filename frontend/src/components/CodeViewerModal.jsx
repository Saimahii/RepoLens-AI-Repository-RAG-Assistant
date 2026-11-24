import { useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import '../styles/CodeViewer.css';
import { ICopy, IFile, IFilter } from '../utils/icons';

const MONACO_LANG_MAP = {
  python: 'python',
  javascript: 'javascript',
  typescript: 'typescript',
  tsx: 'typescript',
  java: 'java',
  go: 'go',
  markdown: 'markdown',
  plaintext: 'plaintext',
};

// Read-only Monaco Editor modal synced with Light/Dark theme and editor preferences
export default function CodeViewerModal({
  viewer,
  onClose,
  theme = 'light',
  editorPrefs = { fontSize: 13, wordWrap: true },
  onAskAboutFile,
}) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const decorationsRef = useRef([]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!viewer) return undefined;
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [viewer, onClose]);

  const applyHighlight = (editor, monaco, startLine, endLine) => {
    if (!editor || !monaco) return;
    if (!startLine) {
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
      editor.setScrollTop(0);
      return;
    }
    const safeStart = Math.max(1, Number(startLine));
    const safeEnd = Math.max(safeStart, Number(endLine || safeStart));

    editor.revealLineInCenter(safeStart);
    editor.setPosition({ lineNumber: safeStart, column: 1 });
    decorationsRef.current = editor.deltaDecorations(decorationsRef.current, [
      {
        range: new monaco.Range(safeStart, 1, safeEnd, 1),
        options: {
          isWholeLine: true,
          className: 'monaco-highlight-line',
          linesDecorationsClassName: 'monaco-highlight-gutter',
        },
      },
    ]);
  };

  useEffect(() => {
    if (!viewer || viewer.loading || viewer.error) return;
    applyHighlight(editorRef.current, monacoRef.current, viewer.startLine, viewer.endLine);
  }, [viewer]);

  if (!viewer) return null;

  const monacoLanguage = MONACO_LANG_MAP[viewer.language] || 'plaintext';
  const monacoTheme = theme === 'dark' ? 'vs-dark' : 'light';

  const handleMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    applyHighlight(editor, monaco, viewer.startLine, viewer.endLine);
  };

  const handleCopy = async () => {
    if (!viewer.content) return;
    try {
      await navigator.clipboard.writeText(viewer.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignore if clipboard access is blocked
    }
  };

  return (
    <div className="code-viewer-backdrop" onClick={onClose}>
      <div className="code-viewer-modal" onClick={(e) => e.stopPropagation()}>
        <div className="code-viewer-header">
          <div className="code-viewer-title">
            <IFile />
            <span className="code-viewer-path">{viewer.path}</span>
            {viewer.startLine && (
              <span className="code-viewer-lines">
                lines {viewer.startLine}
                {viewer.endLine && viewer.endLine !== viewer.startLine ? `–${viewer.endLine}` : ''}
              </span>
            )}
            {viewer.symbolName && (
              <span className="code-viewer-symbol">{viewer.symbolName}</span>
            )}
          </div>

          <div className="code-viewer-actions">
            {viewer.language && <span className="code-viewer-lang">{viewer.language}</span>}
            {!viewer.loading && !viewer.error && onAskAboutFile && (
              <button
                type="button"
                className="code-viewer-btn accent"
                onClick={() => onAskAboutFile(viewer.path)}
                title="Scope chat retrieval to this file"
              >
                <IFilter /> Ask about file
              </button>
            )}
            {!viewer.loading && !viewer.error && (
              <button type="button" className="code-viewer-btn" onClick={handleCopy}>
                <ICopy /> {copied ? 'Copied' : 'Copy file'}
              </button>
            )}
            <button type="button" className="code-viewer-close" onClick={onClose} title="Close (Esc)">
              ✕
            </button>
          </div>
        </div>

        <div className="code-viewer-body">
          {viewer.loading && (
            <div className="code-viewer-state">
              <div className="indexing-spinner" />
              <span>Loading file...</span>
            </div>
          )}

          {!viewer.loading && viewer.error && (
            <div className="code-viewer-state error">
              <span>{viewer.error}</span>
            </div>
          )}

          {!viewer.loading && !viewer.error && (
            <Editor
              height="100%"
              language={monacoLanguage}
              value={viewer.content || ''}
              theme={monacoTheme}
              onMount={handleMount}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                fontSize: editorPrefs.fontSize || 13,
                fontFamily: "'JetBrains Mono', monospace",
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: editorPrefs.wordWrap ? 'on' : 'off',
                automaticLayout: true,
                padding: { top: 12, bottom: 12 },
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
