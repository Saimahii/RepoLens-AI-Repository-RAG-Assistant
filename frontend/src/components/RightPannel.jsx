import '../styles/RightPanel.css';

const TASKS = [
  { label: 'Summarize repository architecture', agent: 'architect' },
  { label: 'Find potential bugs or edge cases', agent: 'bugfinder' },
  { label: 'Explain the main data flow', agent: 'architect' },
  { label: 'Debug common error handling paths', agent: 'debugger' },
];

const QUESTIONS = [
  'What are the main entry points of this codebase?',
  'Explain the core classes and how they interact',
  'Where are routes or public APIs defined?',
  'What external dependencies and patterns are used?',
];

const LANGUAGE_OPTIONS = [
  { value: '', label: 'All languages' },
  { value: 'python', label: 'Python (.py)' },
  { value: 'javascript', label: 'JavaScript (.js)' },
  { value: 'typescript', label: 'TypeScript (.ts)' },
  { value: 'tsx', label: 'TSX (.tsx)' },
  { value: 'java', label: 'Java (.java)' },
  { value: 'go', label: 'Go (.go)' },
  { value: 'markdown', label: 'Markdown (.md)' },
];

// Right panel — Retrieval Filters, Cited Sources in Thread, and Suggested Prompts
export default function RightPanel({
  onTask,
  onQuestion,
  filters,
  onFiltersChange,
  threadSources,
  onOpenSource,
  onOpenFilesDrawer,
  disabled,
}) {
  const hasActiveFilters = Boolean(filters?.language || filters?.path_prefix?.trim());

  return (
    <div className="right-panel">
      {/* ── Retrieval Filters ── */}
      <div className="panel-card">
        <div className="panel-card-header">
          <div className="panel-card-title">Retrieval Filters</div>
          {hasActiveFilters && (
            <button
              type="button"
              className="panel-link-btn"
              onClick={() => onFiltersChange({ language: '', path_prefix: '' })}
            >
              Clear
            </button>
          )}
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-language">
            Language
          </label>
          <select
            id="filter-language"
            className="filter-input"
            value={filters?.language || ''}
            onChange={(e) => onFiltersChange({ ...filters, language: e.target.value })}
          >
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-path">
            Path prefix
          </label>
          <input
            id="filter-path"
            className="filter-input"
            value={filters?.path_prefix || ''}
            onChange={(e) => onFiltersChange({ ...filters, path_prefix: e.target.value })}
            placeholder="e.g. src/ or app/api/"
          />
        </div>
      </div>

      {/* ── Cited Sources in Current Thread ── */}
      <div className="panel-card">
        <div className="panel-card-header">
          <div className="panel-card-title">Cited Sources ({threadSources?.length || 0})</div>
          {onOpenFilesDrawer && (
            <button type="button" className="panel-link-btn" onClick={onOpenFilesDrawer}>
              Browse files
            </button>
          )}
        </div>

        {threadSources?.length > 0 ? (
          <div className="thread-sources-list">
            {threadSources.map((src) => (
              <button
                type="button"
                key={`${src.file_path}:${src.start_line}-${src.end_line}`}
                className="thread-source-btn"
                onClick={() => onOpenSource(src)}
                title={`Open ${src.file_path} (lines ${src.start_line}-${src.end_line})`}
              >
                <span className="thread-source-path">{src.file_path}</span>
                <span className="thread-source-range">
                  L{src.start_line}–{src.end_line}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div className="panel-empty">
            Sources cited in this conversation will appear here for quick jumping into Monaco.
          </div>
        )}
      </div>

      {/* ── Suggested Tasks ── */}
      <div className="panel-card">
        <div className="panel-card-title">Suggested tasks</div>
        <div className="task-chips">
          {TASKS.map((task) => (
            <button
              type="button"
              key={task.label}
              className="task-chip"
              disabled={disabled}
              onClick={() => onTask(task.label)}
            >
              <span className={`agent-dot ${task.agent}`} />
              <span>{task.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Suggested Questions ── */}
      <div className="panel-card">
        <div className="panel-card-title">Suggested questions</div>
        <div className="question-chips">
          {QUESTIONS.map((q) => (
            <button
              type="button"
              key={q}
              className="question-chip"
              disabled={disabled}
              onClick={() => onQuestion(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
