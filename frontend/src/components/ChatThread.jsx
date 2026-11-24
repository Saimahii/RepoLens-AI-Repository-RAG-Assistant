import { useEffect, useMemo, useRef } from 'react';
import '../styles/ChatThread.css';
import AIMessage from './AIMessage';
import { ISearch, IX } from '../utils/icons';

// Renders the chat messages, optional live search bar, thinking state, and error banner
export default function ChatThread({
  messages,
  showSources,
  loading,
  loadingHistory,
  error,
  onDismissError,
  onOpenSource,
  onRewrite,
  indexingStep,
  repoName,
  searchOpen,
  searchQuery,
  onSearchChange,
  onCloseSearch,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!searchQuery) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading, searchQuery]);

  const visibleMessages = useMemo(() => {
    const q = (searchQuery || '').trim().toLowerCase();
    if (!searchOpen || !q) return messages;
    return messages.filter((msg) => {
      const contentMatch = String(msg.content || '').toLowerCase().includes(q);
      const sourceMatch = (msg.sources || []).some((s) =>
        String(s.file_path || '').toLowerCase().includes(q)
      );
      return contentMatch || sourceMatch;
    });
  }, [messages, searchOpen, searchQuery]);

  const isIndexing = indexingStep && indexingStep !== 'done' && indexingStep !== 'failed';

  return (
    <>
      {searchOpen && (
        <div className="chat-search-bar">
          <ISearch />
          <input
            autoFocus
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter messages or file names in this thread..."
          />
          {searchQuery && (
            <span className="chat-search-count">
              {visibleMessages.length} / {messages.length}
            </span>
          )}
          <button
            type="button"
            className="drawer-close"
            onClick={onCloseSearch}
            title="Close search"
          >
            <IX />
          </button>
        </div>
      )}

      <div className="chat-messages">
        <div className="chat-messages-inner">
          {loadingHistory && (
            <div className="chat-empty-state">
              <div className="indexing-spinner" />
              <span>Loading chat history...</span>
            </div>
          )}

          {!loadingHistory && messages.length === 0 && !loading && (
            <div className="chat-empty-state">
              {isIndexing ? (
                <span>
                  Indexing <strong>{repoName || 'repository'}</strong>... You can ask questions as
                  soon as it finishes.
                </span>
              ) : indexingStep === 'failed' ? (
                <span>Indexing failed. Check the error bar above and click Retry Index.</span>
              ) : (
                <span>
                  <strong>{repoName || 'Repository'}</strong> is ready. Ask any question below, open
                  the <strong>File Explorer</strong> or <strong>Chat History</strong> from the left
                  sidebar, or click a suggested prompt on the right.
                </span>
              )}
            </div>
          )}

          {!loadingHistory && messages.length > 0 && visibleMessages.length === 0 && (
            <div className="chat-empty-state">
              <span>No messages in this thread match &ldquo;{searchQuery}&rdquo;.</span>
            </div>
          )}

          {visibleMessages.map((msg) => (
            <div key={msg.id} className="msg">
              {msg.role === 'user' && (
                <div className="msg-user">
                  <div className="msg-user-bubble">{msg.content}</div>
                </div>
              )}

              {(msg.role === 'assistant' || msg.role === 'ai') && (
                <AIMessage
                  msg={msg}
                  showSources={showSources}
                  onOpenSource={onOpenSource}
                  onRewrite={onRewrite}
                />
              )}
            </div>
          ))}

          {loading && (
            <div className="msg">
              <div className="msg-thinking">
                <div className="indexing-spinner" />
                <span>Searching code chunks and generating answer...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="chat-error-banner" role="alert">
              <span>{error}</span>
              {onDismissError && (
                <button type="button" className="chat-error-close" onClick={onDismissError}>
                  ✕
                </button>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>
    </>
  );
}
