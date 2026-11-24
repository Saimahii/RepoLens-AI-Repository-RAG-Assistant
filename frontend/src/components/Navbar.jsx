import { useEffect, useRef, useState } from 'react';
import '../styles/Navbar.css';
import {
  IChevdown,
  IGit,
  IPanelRight,
  IPlus,
  ISearch,
  IShare,
} from '../utils/icons';

export const AGENT_MODES = [
  { id: 'auto', label: 'Auto Agent', desc: 'Backend routes automatically by question' },
  { id: 'explainer', label: 'Code Explainer', desc: 'Explain functions, classes & APIs' },
  { id: 'architect', label: 'Architecture', desc: 'Project structure, modules & data flow' },
  { id: 'bugfinder', label: 'Bug Finder', desc: 'Spot risky patterns, edge cases & bugs' },
  { id: 'debugger', label: 'Debugger', desc: 'Diagnose errors & suggest concrete fixes' },
];

// Top navigation bar with live API status, working agent mode selector, search, share, and panel toggle
export default function Navbar({
  repoName,
  agentMode,
  onChangeAgentMode,
  healthStatus,
  onCheckHealth,
  onOpenRepos,
  searchOpen,
  onToggleSearch,
  onShareThread,
  hasMessages,
  onNewChat,
  rightPanelOpen,
  onToggleRightPanel,
  showChatControls,
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!dropdownOpen) return undefined;
    const handleOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [dropdownOpen]);

  const currentMode = AGENT_MODES.find((m) => m.id === agentMode) || AGENT_MODES[0];

  return (
    <div className="navbar">
      {/* Left: Agent Mode dropdown + live API health indicator */}
      <div className="navbar-left">
        <div className="navbar-select-wrap" ref={menuRef}>
          <button
            type="button"
            className="navbar-select"
            onClick={() => setDropdownOpen((o) => !o)}
            title="Select agent routing mode"
          >
            <span>⬡</span> {currentMode.label} <IChevdown />
          </button>

          {dropdownOpen && (
            <div className="navbar-dropdown">
              {AGENT_MODES.map((mode) => (
                <button
                  type="button"
                  key={mode.id}
                  className={`navbar-dropdown-item ${agentMode === mode.id ? 'active' : ''}`}
                  onClick={() => {
                    onChangeAgentMode(mode.id);
                    setDropdownOpen(false);
                  }}
                >
                  <div className="dropdown-item-title">{mode.label}</div>
                  <div className="dropdown-item-desc">{mode.desc}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          className="navbar-health"
          onClick={onCheckHealth}
          title="Click to refresh FastAPI & MySQL connection status"
        >
          <span
            className={`health-dot ${
              healthStatus.ok ? 'ok' : healthStatus.checking ? 'checking' : 'err'
            }`}
            style={{ marginRight: 0 }}
          />
          {healthStatus.checking ? 'API...' : healthStatus.ok ? 'API Live' : 'API Offline'}
        </button>
      </div>

      {/* Center breadcrumb — clickable to open Repositories drawer */}
      <div className="navbar-breadcrumb">
        <button
          type="button"
          className="breadcrumb-btn"
          onClick={onOpenRepos}
          title="Open Repositories drawer"
        >
          <IGit />
          {repoName ? (
            <>
              <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>Repository /</span>
              <span>{repoName}</span>
            </>
          ) : (
            <span style={{ color: 'var(--text-muted)' }}>Select or connect repository</span>
          )}
        </button>
      </div>

      {/* Right action buttons */}
      <div className="navbar-actions">
        {showChatControls && (
          <>
            <button
              type="button"
              className={`btn-ghost ${searchOpen ? 'active' : ''}`}
              onClick={onToggleSearch}
              disabled={!hasMessages}
              title="Search messages in this thread"
            >
              <ISearch /> Search
            </button>
            <button
              type="button"
              className="btn-ghost"
              onClick={onShareThread}
              disabled={!hasMessages}
              title="Copy full conversation as Markdown"
            >
              <IShare /> Share
            </button>
          </>
        )}

        <button type="button" className="btn-primary" onClick={onNewChat}>
          <IPlus /> New Thread
        </button>

        {showChatControls && (
          <button
            type="button"
            className={`btn-ghost ${rightPanelOpen ? 'active' : ''}`}
            onClick={onToggleRightPanel}
            title={rightPanelOpen ? 'Hide right panel' : 'Show right panel'}
          >
            <IPanelRight />
          </button>
        )}
      </div>
    </div>
  );
}
