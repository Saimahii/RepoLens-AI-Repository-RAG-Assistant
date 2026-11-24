import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ── Global styles ──
import './styles/Global.css';

// ── Components ──
import Sidebar from './components/Sidebar';
import LeftDrawer from './components/LeftDrawer';
import Navbar from './components/Navbar';
import IndexingBar from './components/Indexingbar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatThread from './components/ChatThread';
import MessageInput from './components/MessageInput';
import RightPanel from './components/RightPannel';
import CodeViewerModal from './components/CodeViewerModal';

// ── Real FastAPI client ──
import {
  API_BASE_URL,
  askChat,
  checkHealth,
  extractErrorMessage,
  getChatHistory,
  getChatSessions,
  getRepoFile,
  getRepoFiles,
  getRepoStatus,
  indexRepo,
  uploadRepo,
} from './services/api';

const POLL_INTERVAL_MS = 1200;
const STORAGE_THEME = 'repolens_theme';
const STORAGE_REPOS = 'repolens_recent_repos';
const STORAGE_EDITOR = 'repolens_editor_prefs';

function extractRepoName(url) {
  const clean = url.trim().replace(/\/+$/, '').replace(/\.git$/i, '');
  return clean.split('/').pop() || 'repository';
}

function readJsonStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

// Prefix question gently only when user explicitly overrides Auto Agent mode
// (keeps backend keyword routing untouched while making the Agent Mode selector work!)
function applyAgentModeHint(question, agentMode) {
  if (!agentMode || agentMode === 'auto' || agentMode === 'explainer') {
    return question;
  }
  const lower = question.toLowerCase();
  if (agentMode === 'bugfinder' && !/\b(bugs?|issues?|problems?)\b/.test(lower)) {
    return `Find potential bugs or issues: ${question}`;
  }
  if (agentMode === 'debugger' && !/\b(debug\w*|errors?|fix\w*)\b/.test(lower)) {
    return `Debug and suggest a fix: ${question}`;
  }
  if (agentMode === 'architect' && !/\b(architecture|flows?|structures?)\b/.test(lower)) {
    return `Explain the architecture and flow: ${question}`;
  }
  return question;
}

// ─────────────────────────────────────────────
// App — root component powering full interactive RepoLens workspace
// ─────────────────────────────────────────────
export default function App() {
  // Appearance & workspace chrome
  const [theme, setTheme] = useState(() => localStorage.getItem(STORAGE_THEME) || 'light');
  const [activeNav, setActiveNav] = useState('home'); // 'home' | 'chat'
  const [openDrawer, setOpenDrawer] = useState(null); // null | 'repos' | 'history' | 'files' | 'settings'
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [editorPrefs, setEditorPrefs] = useState(() =>
    readJsonStorage(STORAGE_EDITOR, { fontSize: 13, wordWrap: true })
  );
  const [toast, setToast] = useState(null);

  // Live backend health indicator
  const [healthStatus, setHealthStatus] = useState({ ok: false, database: 'unknown', checking: true });

  // Connected repository & indexing state
  const [recentRepos, setRecentRepos] = useState(() => readJsonStorage(STORAGE_REPOS, []));
  const [repoId, setRepoId] = useState(null);
  const [repoName, setRepoName] = useState(null);
  const [repoUrl, setRepoUrl] = useState(null);
  const [indexingStep, setIndexingStep] = useState(null);
  const [indexingError, setIndexingError] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  // Chat, search, and agent mode state
  const [agentMode, setAgentMode] = useState('auto');
  const [sessionId, setSessionId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [citation, setCitation] = useState(true);
  const [chatLoading, setChatLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [chatError, setChatError] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // File tree, retrieval filters, and Monaco modal
  const [fileTree, setFileTree] = useState([]);
  const [filters, setFilters] = useState({ language: '', path_prefix: '' });
  const [codeViewer, setCodeViewer] = useState(null);

  const pollTimerRef = useRef(null);
  const pendingQuestionRef = useRef(null);
  const toastTimerRef = useRef(null);

  const showToast = useCallback((message) => {
    setToast(message);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 2400);
  }, []);

  // Sync light/dark theme attribute to document root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_THEME, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(STORAGE_EDITOR, JSON.stringify(editorPrefs));
  }, [editorPrefs]);

  useEffect(() => {
    localStorage.setItem(STORAGE_REPOS, JSON.stringify(recentRepos));
  }, [recentRepos]);

  // Check backend health on startup (and on manual refresh)
  const refreshHealth = useCallback(async (announce = false) => {
    setHealthStatus((prev) => ({ ...prev, checking: true }));
    try {
      const data = await checkHealth();
      const ok = data.status === 'ok' && data.database === 'ok';
      setHealthStatus({ ok, database: data.database || 'ok', checking: false });
      if (announce) showToast(ok ? 'Backend & MySQL connected' : 'Backend reachable, MySQL issue');
    } catch {
      setHealthStatus({ ok: false, database: 'unreachable', checking: false });
      if (announce) showToast('Could not reach FastAPI backend');
    }
  }, [showToast]);

  useEffect(() => {
    refreshHealth(false);
  }, [refreshHealth]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const rememberRepo = useCallback((url, name, id) => {
    setRecentRepos((prev) => {
      const filtered = prev.filter((r) => r.url.toLowerCase() !== url.toLowerCase());
      return [{ url, name, repoId: id }, ...filtered].slice(0, 10);
    });
  }, []);

  const handleRemoveRepo = (url) => {
    setRecentRepos((prev) => prev.filter((r) => r.url.toLowerCase() !== url.toLowerCase()));
  };

  // Load file tree & saved sessions for an indexed repo
  const loadRepoArtifacts = useCallback(async (targetRepoId) => {
    try {
      const [tree, sessionList] = await Promise.all([
        getRepoFiles(targetRepoId),
        getChatSessions(targetRepoId),
      ]);
      setFileTree(tree);
      setSessions(sessionList);
    } catch (error) {
      setChatError(extractErrorMessage(error, 'Could not load repository files or chat history.'));
    }
  }, []);

  // Send a natural-language question to POST /chat/ask
  const handleSend = useCallback(
    async (text, overrideRepoId = null, overrideSessionId = undefined) => {
      const activeRepo = overrideRepoId || repoId;
      const activeSession = overrideSessionId !== undefined ? overrideSessionId : sessionId;

      if (!activeRepo) {
        setUploadError('Connect and index a GitHub repository first.');
        setActiveNav('home');
        return;
      }
      if (indexingStep && indexingStep !== 'done' && !overrideRepoId) {
        setChatError('Please wait for repository indexing to finish before asking questions.');
        return;
      }

      setChatError(null);
      setActiveNav('chat');
      const finalQuestion = applyAgentModeHint(text, agentMode);

      const tempUserId = `user-${Date.now()}`;
      setMessages((prev) => [...prev, { id: tempUserId, role: 'user', content: text }]);
      setChatLoading(true);

      try {
        const response = await askChat({
          repoId: activeRepo,
          sessionId: activeSession,
          question: finalQuestion,
          filters,
        });

        setSessionId(response.session_id);
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            agent: response.agent,
            content: response.answer,
            sources: response.sources || [],
          },
        ]);

        getChatSessions(activeRepo)
          .then(setSessions)
          .catch(() => {});
      } catch (error) {
        setChatError(extractErrorMessage(error, 'Failed to get an answer from RepoLens.'));
      } finally {
        setChatLoading(false);
      }
    },
    [repoId, sessionId, indexingStep, agentMode, filters]
  );

  // Poll GET /repo/status/{repo_id} until done or failed
  const startStatusPolling = useCallback(
    (targetRepoId) => {
      stopPolling();

      const pollOnce = async () => {
        try {
          const data = await getRepoStatus(targetRepoId);
          setIndexingStep(data.step || data.status);

          if (data.status === 'done') {
            stopPolling();
            setIndexingError(null);
            await loadRepoArtifacts(targetRepoId);
            showToast('Repository indexed and ready');

            if (pendingQuestionRef.current) {
              const queued = pendingQuestionRef.current;
              pendingQuestionRef.current = null;
              handleSend(queued, targetRepoId, null);
            }
          } else if (data.status === 'failed') {
            stopPolling();
            setIndexingError(data.error || 'Indexing failed.');
            pendingQuestionRef.current = null;
          }
        } catch (error) {
          stopPolling();
          setIndexingStep('failed');
          setIndexingError(extractErrorMessage(error, 'Lost connection while polling indexing status.'));
          pendingQuestionRef.current = null;
        }
      };

      pollOnce();
      pollTimerRef.current = setInterval(pollOnce, POLL_INTERVAL_MS);
    },
    [stopPolling, loadRepoArtifacts, handleSend, showToast]
  );

  // Connect / upload / index a GitHub repository
  const handleIndexRepo = async (url, queuedQuestion = null) => {
    setUploadLoading(true);
    setUploadError(null);
    setChatError(null);
    setIndexingError(null);
    pendingQuestionRef.current = queuedQuestion;

    try {
      const uploaded = await uploadRepo(url);
      const id = uploaded.repo_id;
      const name = extractRepoName(url);

      setRepoId(id);
      setRepoName(name);
      setRepoUrl(url.trim());
      rememberRepo(url.trim(), name, id);

      setSessionId(null);
      setMessages([]);
      setFileTree([]);
      setSessions([]);
      setSearchOpen(false);
      setSearchQuery('');
      setFilters({ language: '', path_prefix: '' });
      setActiveNav('chat');
      setOpenDrawer(null);

      if (uploaded.status === 'done') {
        setIndexingStep('done');
        await loadRepoArtifacts(id);
        showToast(`Loaded ${name}`);
        if (pendingQuestionRef.current) {
          const nextQ = pendingQuestionRef.current;
          pendingQuestionRef.current = null;
          handleSend(nextQ, id, null);
        }
      } else {
        setIndexingStep('parsing');
        await indexRepo(id);
        startStatusPolling(id);
      }
    } catch (error) {
      pendingQuestionRef.current = null;
      const msg = extractErrorMessage(error, 'Could not upload repository.');
      setUploadError(msg);
      showToast(msg);
    } finally {
      setUploadLoading(false);
    }
  };

  // Re-index active repository
  const handleReindex = async () => {
    if (!repoId) return;
    setIndexingError(null);
    setIndexingStep('parsing');
    try {
      await indexRepo(repoId);
      startStatusPolling(repoId);
    } catch (error) {
      setIndexingStep('failed');
      setIndexingError(extractErrorMessage(error, 'Could not start re-indexing.'));
    }
  };

  // Left sidebar navigation handler — EVERY icon works!
  const handleSelectNav = (id) => {
    if (id === 'home') {
      setActiveNav('home');
      setOpenDrawer(null);
      return;
    }
    if (id === 'chat') {
      if (repoId) {
        setActiveNav('chat');
        setOpenDrawer(null);
      } else {
        setOpenDrawer('repos');
        showToast('Select or connect a repository to open Chat');
      }
      return;
    }
    // Toggle drawer panels: history, repos, files, settings
    setOpenDrawer((prev) => (prev === id ? null : id));
  };

  // Start a new chat session on the connected repo
  const handleNewSession = () => {
    if (!repoId) {
      setActiveNav('home');
      setOpenDrawer(null);
      return;
    }
    setSessionId(null);
    setMessages([]);
    setChatError(null);
    setSearchOpen(false);
    setSearchQuery('');
    setActiveNav('chat');
    showToast('Started new chat thread');
  };

  // Load saved session from GET /chat/history
  const handleSelectSession = async (targetSessionId) => {
    if (!targetSessionId) return;
    setLoadingHistory(true);
    setChatError(null);
    setSessionId(targetSessionId);
    setActiveNav('chat');
    setSearchOpen(false);
    setSearchQuery('');
    try {
      const history = await getChatHistory(targetSessionId);
      setMessages(history);
    } catch (error) {
      setChatError(extractErrorMessage(error, 'Could not load chat history.'));
    } finally {
      setLoadingHistory(false);
    }
  };

  // Re-ask the user question preceding an AI answer
  const handleRewrite = (aiMsg) => {
    if (chatLoading) return;
    const idx = messages.findIndex((m) => m.id === aiMsg.id);
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        handleSend(messages[i].content);
        return;
      }
    }
  };

  // Copy entire chat thread as Markdown (Share button in Navbar)
  const handleShareThread = async () => {
    if (!messages.length) return;
    const md = [
      `# RepoLens Thread — ${repoName || 'Repository'}`,
      '',
      ...messages.map((m) => {
        if (m.role === 'user') return `## User\n\n${m.content}\n`;
        const srcs = (m.sources || [])
          .map((s) => `- \`${s.file_path}:${s.start_line}-${s.end_line}\``)
          .join('\n');
        return `## RepoLens (${m.agent || 'explainer'})\n\n${m.content}\n${srcs ? `\n**Sources:**\n${srcs}\n` : ''}`;
      }),
    ].join('\n');

    try {
      await navigator.clipboard.writeText(md);
      showToast('Copied conversation as Markdown');
    } catch {
      showToast('Clipboard blocked by browser');
    }
  };

  // Open a source chip or file inside the Monaco Editor modal
  const handleOpenFile = async (filePath, options = {}) => {
    if (!repoId || !filePath) return;
    setCodeViewer({
      path: filePath,
      language: options.language || '',
      content: '',
      startLine: options.startLine || null,
      endLine: options.endLine || null,
      symbolName: options.symbolName || null,
      loading: true,
      error: null,
    });

    try {
      const fileData = await getRepoFile(repoId, filePath);
      setCodeViewer({
        path: fileData.path,
        language: fileData.language,
        content: fileData.content,
        startLine: options.startLine || null,
        endLine: options.endLine || null,
        symbolName: options.symbolName || null,
        loading: false,
        error: null,
      });
    } catch (error) {
      setCodeViewer((prev) =>
        prev
          ? { ...prev, loading: false, error: extractErrorMessage(error, 'Could not open file.') }
          : null
      );
    }
  };

  const handleOpenSource = (source) => {
    handleOpenFile(source.file_path, {
      language: source.language,
      startLine: source.start_line,
      endLine: source.end_line,
      symbolName: source.symbol_name,
    });
  };

  // "Ask about file" inside Monaco modal scopes path_prefix to that file
  const handleAskAboutFile = (filePath) => {
    setFilters((prev) => ({ ...prev, path_prefix: filePath }));
    setCodeViewer(null);
    setActiveNav('chat');
    showToast(`Scoped search to ${filePath}`);
  };

  // Unique cited sources across the active thread (for RightPanel quick-jump card)
  const threadSources = useMemo(() => {
    const map = new Map();
    for (const msg of messages) {
      for (const src of msg.sources || []) {
        const key = `${src.file_path}:${src.start_line}-${src.end_line}`;
        if (!map.has(key)) map.set(key, src);
      }
    }
    return Array.from(map.values());
  }, [messages]);

  const inChatView = activeNav === 'chat' && Boolean(repoId);
  const isRepoReady = Boolean(repoId) && indexingStep === 'done';
  const inputDisabled = !inChatView || !isRepoReady || chatLoading;

  const inputPlaceholder = !inChatView
    ? 'Connect a GitHub repository above to start chatting...'
    : !isRepoReady
    ? 'Waiting for repository indexing to finish...'
    : chatLoading
    ? 'RepoLens is thinking...'
    : `Ask anything about ${repoName || 'the repository'}... (Shift+Enter for new line)`;

  return (
    <div className="app">
      {/* ── Left icon rail ── */}
      <Sidebar
        activeNav={activeNav}
        openDrawer={openDrawer}
        onSelectNav={handleSelectNav}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        sessionCount={sessions.length}
        repoCount={recentRepos.length}
      />

      {/* ── Slide-out Left Drawer (Repositories / Chat History / File Explorer / Settings) ── */}
      <LeftDrawer
        panel={openDrawer}
        onClose={() => setOpenDrawer(null)}
        recentRepos={recentRepos}
        activeRepoUrl={repoUrl}
        onConnectRepo={handleIndexRepo}
        onRemoveRepo={handleRemoveRepo}
        uploadLoading={uploadLoading}
        repoName={repoName}
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        fileTree={fileTree}
        activeFilePath={codeViewer?.path || null}
        onSelectFile={(path) => handleOpenFile(path)}
        theme={theme}
        onSetTheme={setTheme}
        citation={citation}
        setCitation={setCitation}
        editorPrefs={editorPrefs}
        onUpdateEditorPrefs={setEditorPrefs}
        healthStatus={healthStatus}
        onCheckHealth={() => refreshHealth(true)}
        apiBaseUrl={API_BASE_URL}
      />

      {/* ── Main area (navbar + content) ── */}
      <div className="main">
        <Navbar
          repoName={repoName}
          agentMode={agentMode}
          onChangeAgentMode={setAgentMode}
          healthStatus={healthStatus}
          onCheckHealth={() => refreshHealth(true)}
          onOpenRepos={() => setOpenDrawer((d) => (d === 'repos' ? null : 'repos'))}
          searchOpen={searchOpen}
          onToggleSearch={() => {
            setSearchOpen((prev) => {
              if (prev) setSearchQuery('');
              return !prev;
            });
          }}
          onShareThread={handleShareThread}
          hasMessages={messages.length > 0}
          onNewChat={handleNewSession}
          rightPanelOpen={rightPanelOpen}
          onToggleRightPanel={() => setRightPanelOpen((o) => !o)}
          showChatControls={inChatView}
        />

        <div className="content">
          {/* Center column */}
          <div className="chat-area">
            {inChatView && indexingStep && (
              <IndexingBar
                step={indexingStep}
                error={indexingError}
                onReindex={handleReindex}
              />
            )}

            {!inChatView ? (
              <WelcomeScreen
                onIndexRepo={handleIndexRepo}
                isUploading={uploadLoading}
                error={uploadError}
                recentRepos={recentRepos}
                onOpenReposDrawer={() => setOpenDrawer('repos')}
              />
            ) : (
              <ChatThread
                messages={messages}
                showSources={citation}
                loading={chatLoading}
                loadingHistory={loadingHistory}
                error={chatError}
                onDismissError={() => setChatError(null)}
                onOpenSource={handleOpenSource}
                onRewrite={handleRewrite}
                indexingStep={indexingStep}
                repoName={repoName}
                searchOpen={searchOpen}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                onCloseSearch={() => {
                  setSearchOpen(false);
                  setSearchQuery('');
                }}
              />
            )}

            {inChatView && (
              <MessageInput
                onSend={handleSend}
                citation={citation}
                setCitation={setCitation}
                disabled={inputDisabled}
                placeholder={inputPlaceholder}
                filters={filters}
                onClearFilter={(field) => setFilters((prev) => ({ ...prev, [field]: '' }))}
                agentMode={agentMode}
                onResetAgentMode={() => setAgentMode('auto')}
              />
            )}
          </div>

          {/* Collapsible Right Panel */}
          {inChatView && rightPanelOpen && (
            <RightPanel
              onTask={handleSend}
              onQuestion={handleSend}
              filters={filters}
              onFiltersChange={setFilters}
              threadSources={threadSources}
              onOpenSource={handleOpenSource}
              onOpenFilesDrawer={() => setOpenDrawer('files')}
              disabled={!isRepoReady || chatLoading}
            />
          )}
        </div>
      </div>

      {/* ── Monaco Editor code viewer modal ── */}
      <CodeViewerModal
        viewer={codeViewer}
        onClose={() => setCodeViewer(null)}
        theme={theme}
        editorPrefs={editorPrefs}
        onAskAboutFile={handleAskAboutFile}
      />

      {/* ── Toast notification ── */}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
