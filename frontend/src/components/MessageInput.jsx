import { useRef, useState } from 'react';
import '../styles/MessageInput.css';
import { IArrowup } from '../utils/icons';

// Bottom input bar with active filter/agent pills, auto-growing textarea, citation toggle, and send button
export default function MessageInput({
  onSend,
  citation,
  setCitation,
  disabled,
  placeholder,
  filters,
  onClearFilter,
  agentMode,
  onResetAgentMode,
}) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  const resetHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleChange = (e) => {
    setValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
  };

  const handleSubmit = () => {
    if (disabled) return;
    if (value.trim()) {
      onSend(value.trim());
      setValue('');
      resetHeight();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasPills =
    Boolean(filters?.language) ||
    Boolean(filters?.path_prefix?.trim()) ||
    (agentMode && agentMode !== 'auto');

  return (
    <div className="input-wrap">
      {hasPills && (
        <div className="input-meta-row">
          {agentMode && agentMode !== 'auto' && (
            <span className="input-pill">
              agent:{agentMode}
              <button type="button" onClick={onResetAgentMode} title="Reset to Auto Agent">
                ✕
              </button>
            </span>
          )}
          {filters?.language && (
            <span className="input-pill">
              lang:{filters.language}
              <button type="button" onClick={() => onClearFilter('language')} title="Clear language filter">
                ✕
              </button>
            </span>
          )}
          {filters?.path_prefix?.trim() && (
            <span className="input-pill">
              path:{filters.path_prefix.trim()}
              <button type="button" onClick={() => onClearFilter('path_prefix')} title="Clear path filter">
                ✕
              </button>
            </span>
          )}
        </div>
      )}

      <div className={`input-bar ${disabled ? 'disabled' : ''}`}>
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder || 'Ask anything about the repository... (Shift+Enter for new line)'}
        />

        {/* Citation toggle */}
        <div
          className="citation-toggle"
          onClick={() => setCitation(!citation)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setCitation(!citation)}
        >
          <div className={`toggle-pill ${citation ? 'on' : ''}`} />
          <span>Citations</span>
        </div>

        {/* Send button */}
        <button
          type="button"
          className="send-btn"
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          title="Send question (Enter)"
        >
          <IArrowup />
        </button>
      </div>
    </div>
  );
}
