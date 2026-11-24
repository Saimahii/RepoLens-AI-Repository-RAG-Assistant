import { useMemo, useState } from 'react';
import '../styles/Drawer.css';
import {
  IFolder,
  IHistory,
  IMoon,
  IPlus,
  ISearch,
  ISun,
  ITrash,
  IX,
} from '../utils/icons';

const LANG_DOT_MAP = {
  python: 'lang-py',
  javascript: 'lang-js',
  typescript: 'lang-ts',
  tsx: 'lang-ts',
  markdown: 'lang-md',
  go: 'lang-go',
  java: 'lang-java',
};

// Recursively collect every folder path in a tree (for Expand All)
function collectFolderPaths(nodes, acc = []) {
  for (const node of nodes || []) {
    if (node.type === 'folder') {
      acc.push(node.path);
      collectFolderPaths(node.children, acc);
    }
  }
  return acc;
}

// Recursively filter a file tree by search query (keeping matching files + ancestor folders)
function filterTree(nodes, query) {
  if (!query) return nodes || [];
  const q = query.toLowerCase();
  const out = [];
  for (const node of nodes || []) {
    if (node.type === 'file') {
      if (node.path.toLowerCase().includes(q) || node.name.toLowerCase().includes(q)) {
        out.push(node);
      }
    } else {
      const matchedChildren = filterTree(node.children, q);
      if (matchedChildren.length > 0 || node.name.toLowerCase().includes(q)) {
        out.push({ ...node, children: matchedChildren });
      }
    }
  }
  return out;
}

function DrawerTreeNode({ node, depth, expanded, forceOpen, onToggle, activeFilePath, onSelectFile }) {
  const isFolder = node.type === 'folder';
  const isOpen = forceOpen || expanded.has(node.path);
  const isActive = !isFolder && activeFilePath === node.path;
  const dotClass = LANG_DOT_MAP[node.language] || 'lang-default';

  const handleClick = () => {
    if (isFolder) onToggle(node.path);
    else if (onSelectFile) onSelectFile(node.path);
  };

  return (
    <>
      <div
        className={`file-tree-item ${isActive ? 'active' : ''}`}
        style={{ paddingLeft: 6 + depth * 13 }}
        onClick={handleClick}
        title={node.path}
      >
        {isFolder ? (
          <>
            <span className="tree-caret">{isOpen ? '▾' : '▸'}</span>
            <IFolder />
          </>
        ) : (
          <span className={`lang-dot ${dotClass}`} />
        )}
        <span className="file-tree-name">{node.name}</span>
      </div>

      {isFolder && isOpen && node.children?.length > 0 && (
        <div>
          {node.children.map((child) => (
            <DrawerTreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              forceOpen={forceOpen}
              onToggle={onToggle}
              activeFilePath={activeFilePath}
              onSelectFile={onSelectFile}
            />
          ))}
        </div>
      )}
    </>
  );
}

// Slide-out drawer powering Repositories, Chat History, File Explorer, and Settings
export default function LeftDrawer({
  panel,
  onClose,
  // Repositories
  recentRepos,
  activeRepoUrl,
  onConnectRepo,
  onRemoveRepo,
  uploadLoading,
  // Chat History
  repoName,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  // File Explorer
  fileTree,
  activeFilePath,
  onSelectFile,
  // Settings
  theme,
  onSetTheme,
  citation,
  setCitation,
  editorPrefs,
  onUpdateEditorPrefs,
  healthStatus,
  onCheckHealth,
  apiBaseUrl,
}) {
  const [repoInput, setRepoInput] = useState('');
  const [historyQuery, setHistoryQuery] = useState('');
  const [fileQuery, setFileQuery] = useState('');
  const [expanded, setExpanded] = useState(() => new Set(['src', 'app', 'backend', 'frontend']));

  const filteredSessions = useMemo(() => {
    const q = historyQuery.trim().toLowerCase();
    if (!q) return sessions || [];
    return (sessions || []).filter((s) => (s.title || '').toLowerCase().includes(q));
  }, [sessions, historyQuery]);

  const filteredTree = useMemo(
    () => filterTree(fileTree, fileQuery.trim()),
    [fileTree, fileQuery]
  );

  if (!panel) return null;

  const toggleFolder = (path) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleAddRepo = (e) => {
    e.preventDefault();
    if (!repoInput.trim() || uploadLoading) return;
    onConnectRepo(repoInput.trim());
    setRepoInput('');
  };

  const titles = {
    repos: { label: 'Repositories', count: recentRepos?.length || 0 },
    history: { label: 'Chat History', count: sessions?.length || 0 },
    files: { label: 'File Explorer', count: null },
    settings: { label: 'Settings', count: null },
  };
  const headerInfo = titles[panel] || { label: '', count: null };

  return (
    <aside className="left-drawer">
      <div className="drawer-header">
        <div className="drawer-title">
          <span>{headerInfo.label}</span>
          {headerInfo.count !== null && (
            <span className="drawer-count">{headerInfo.count}</span>
          )}
        </div>
        <button type="button" className="drawer-close" onClick={onClose} title="Close drawer">
          <IX />
        </button>
      </div>

      <div className="drawer-body">
        {/* ── REPOSITORIES PANEL ── */}
        {panel === 'repos' && (
          <>
            <form className="repo-add-form" onSubmit={handleAddRepo}>
              <input
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                placeholder="https://github.com/owner/repo"
                disabled={uploadLoading}
              />
              <button
                type="submit"
                className="drawer-primary-btn"
                disabled={uploadLoading || !repoInput.trim()}
              >
                <IPlus /> {uploadLoading ? 'Connecting...' : 'Connect & Index'}
              </button>
            </form>

            {recentRepos?.length > 0 ? (
              <div className="repo-card-list">
                {recentRepos.map((repo) => {
                  const isActive =
                    activeRepoUrl &&
                    activeRepoUrl.toLowerCase() === repo.url.toLowerCase();
                  return (
                    <div
                      key={repo.url}
                      className={`repo-card ${isActive ? 'active' : ''}`}
                      onClick={() => onConnectRepo(repo.url)}
                      title={`Open ${repo.url}`}
                    >
                      <div className="repo-card-info">
                        <div className="repo-card-name">{repo.name}</div>
                        <div className="repo-card-url">{repo.url.replace('https://github.com/', '')}</div>
                      </div>
                      <button
                        type="button"
                        className="repo-card-del"
                        title="Remove from list"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveRepo(repo.url);
                        }}
                      >
                        <ITrash />
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="drawer-empty">
                No recent repositories yet. Paste any public GitHub URL above to connect it.
              </div>
            )}
          </>
        )}

        {/* ── CHAT HISTORY PANEL ── */}
        {panel === 'history' && (
          <>
            <button
              type="button"
              className="drawer-primary-btn"
              onClick={onNewSession}
              disabled={!repoName}
            >
              <IPlus /> New Chat Thread
            </button>

            <div className="drawer-search">
              <ISearch />
              <input
                value={historyQuery}
                onChange={(e) => setHistoryQuery(e.target.value)}
                placeholder="Filter sessions..."
              />
            </div>

            {!repoName ? (
              <div className="drawer-empty">
                Connect a repository first to see its saved chat sessions.
              </div>
            ) : filteredSessions.length > 0 ? (
              <div className="history-list">
                {filteredSessions.map((s) => (
                  <button
                    type="button"
                    key={s.id}
                    className={`history-item ${activeSessionId === s.id ? 'active' : ''}`}
                    onClick={() => onSelectSession(s.id)}
                    title={s.title}
                  >
                    <IHistory />
                    <span className="history-item-title">{s.title}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="drawer-empty">
                {historyQuery ? 'No sessions match your filter.' : 'No saved sessions yet. Ask a question to start one!'}
              </div>
            )}
          </>
        )}

        {/* ── FILE EXPLORER PANEL ── */}
        {panel === 'files' && (
          <>
            <div className="drawer-search">
              <ISearch />
              <input
                value={fileQuery}
                onChange={(e) => setFileQuery(e.target.value)}
                placeholder="Search files by path..."
              />
            </div>

            {fileTree?.length > 0 && (
              <div className="drawer-action-row">
                <button
                  type="button"
                  className="drawer-mini-btn"
                  onClick={() => setExpanded(new Set(collectFolderPaths(fileTree)))}
                >
                  Expand all
                </button>
                <button
                  type="button"
                  className="drawer-mini-btn"
                  onClick={() => setExpanded(new Set())}
                >
                  Collapse all
                </button>
              </div>
            )}

            {!repoName ? (
              <div className="drawer-empty">
                Connect and index a repository to browse its source files.
              </div>
            ) : filteredTree.length > 0 ? (
              <div className="drawer-file-tree">
                {filteredTree.map((node) => (
                  <DrawerTreeNode
                    key={node.path}
                    node={node}
                    depth={0}
                    expanded={expanded}
                    forceOpen={Boolean(fileQuery.trim())}
                    onToggle={toggleFolder}
                    activeFilePath={activeFilePath}
                    onSelectFile={onSelectFile}
                  />
                ))}
              </div>
            ) : (
              <div className="drawer-empty">
                {fileQuery ? 'No matching files found.' : 'Files will appear once indexing finishes.'}
              </div>
            )}
          </>
        )}

        {/* ── SETTINGS PANEL ── */}
        {panel === 'settings' && (
          <>
            <div className="setting-card">
              <div className="setting-label">Appearance</div>
              <div className="theme-segmented">
                <button
                  type="button"
                  className={`theme-seg-btn ${theme === 'light' ? 'active' : ''}`}
                  onClick={() => onSetTheme('light')}
                >
                  <ISun /> Light
                </button>
                <button
                  type="button"
                  className={`theme-seg-btn ${theme === 'dark' ? 'active' : ''}`}
                  onClick={() => onSetTheme('dark')}
                >
                  <IMoon /> Dark
                </button>
              </div>
            </div>

            <div className="setting-card">
              <div className="setting-row">
                <div>
                  <div className="setting-label">Show Source Citations</div>
                  <div className="setting-desc">Display clickable file chips above answers</div>
                </div>
                <div
                  className={`toggle-pill ${citation ? 'on' : ''}`}
                  onClick={() => setCitation(!citation)}
                  role="button"
                  tabIndex={0}
                />
              </div>

              <div className="setting-row">
                <div>
                  <div className="setting-label">Monaco Word Wrap</div>
                  <div className="setting-desc">Wrap long lines in the code viewer</div>
                </div>
                <div
                  className={`toggle-pill ${editorPrefs.wordWrap ? 'on' : ''}`}
                  onClick={() =>
                    onUpdateEditorPrefs({ ...editorPrefs, wordWrap: !editorPrefs.wordWrap })
                  }
                  role="button"
                  tabIndex={0}
                />
              </div>

              <div className="setting-row">
                <div className="setting-label">Editor Font Size</div>
                <select
                  className="filter-input"
                  style={{ width: 82 }}
                  value={editorPrefs.fontSize}
                  onChange={(e) =>
                    onUpdateEditorPrefs({ ...editorPrefs, fontSize: Number(e.target.value) })
                  }
                >
                  {[12, 13, 14, 15, 16].map((size) => (
                    <option key={size} value={size}>
                      {size}px
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="setting-card">
              <div className="setting-label">Backend Status</div>
              <div className="health-row">
                <span>
                  <span
                    className={`health-dot ${
                      healthStatus.ok ? 'ok' : healthStatus.checking ? 'checking' : 'err'
                    }`}
                  />
                  {healthStatus.checking
                    ? 'Checking...'
                    : healthStatus.ok
                    ? `Connected (DB: ${healthStatus.database})`
                    : 'Backend unreachable'}
                </span>
                <button type="button" className="drawer-mini-btn" onClick={onCheckHealth}>
                  Refresh
                </button>
              </div>
              <div className="setting-desc" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {apiBaseUrl}
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
