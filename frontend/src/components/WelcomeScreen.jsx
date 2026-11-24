import { useState } from 'react';
import '../styles/WelcomeScreen.css';
import { IGit } from '../utils/icons';

const CHIPS = [
  'Explain the main architecture',
  'Find potential bugs',
  'How does auth work?',
  'Summarize this codebase',
  'Debug this error',
];

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

// Home/welcome state — connect a new GitHub repo or jump back into a recent one
export default function WelcomeScreen({
  onIndexRepo,
  isUploading,
  error,
  recentRepos,
  onOpenReposDrawer,
}) {
  const [repoUrl, setRepoUrl] = useState('');
  const [chipHint, setChipHint] = useState('');

  const handleIndex = () => {
    if (isUploading) return;
    if (!repoUrl.trim()) {
      setChipHint('Paste a public GitHub repository URL above first.');
      return;
    }
    setChipHint('');
    onIndexRepo(repoUrl.trim());
  };

  const handleChipClick = (chip) => {
    if (repoUrl.trim()) {
      setChipHint('');
      onIndexRepo(repoUrl.trim(), chip);
      return;
    }
    if (recentRepos?.length > 0) {
      setChipHint('');
      onIndexRepo(recentRepos[0].url, chip);
      return;
    }
    setChipHint('Paste a public GitHub repository URL above first, then click a prompt.');
  };

  return (
    <div className="welcome">
      <div className="orb" />

      <div className="welcome-title">
        {getGreeting()}, Dev
        <br />
        What&apos;s on <em>your mind?</em>
      </div>

      <div className="welcome-subtitle">
        Connect any public GitHub repository to parse its AST, search semantically, and inspect cited lines in Monaco Editor.
      </div>

      {/* Repo URL input */}
      <div className="repo-input-section">
        <div className="repo-input-label">Connect a GitHub Repository</div>
        <div className="repo-url-bar">
          <IGit />
          <input
            value={repoUrl}
            onChange={(e) => {
              setRepoUrl(e.target.value);
              if (chipHint) setChipHint('');
            }}
            placeholder="https://github.com/owner/repository"
            disabled={isUploading}
            onKeyDown={(e) => e.key === 'Enter' && handleIndex()}
          />
          <button
            type="button"
            className="btn-index"
            onClick={handleIndex}
            disabled={isUploading}
          >
            {isUploading ? 'Connecting...' : 'Index →'}
          </button>
        </div>

        {(error || chipHint) && (
          <div className={`welcome-feedback ${error ? 'error' : 'hint'}`}>
            {error || chipHint}
          </div>
        )}
      </div>

      {/* Recent Repositories — 1-click reconnect */}
      {recentRepos?.length > 0 && (
        <div className="recent-repos-section">
          <div className="repo-input-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Recent Repositories</span>
            {onOpenReposDrawer && (
              <button
                type="button"
                className="panel-link-btn"
                onClick={onOpenReposDrawer}
              >
                Manage all
              </button>
            )}
          </div>
          <div className="recent-repos-row">
            {recentRepos.slice(0, 4).map((repo) => (
              <button
                type="button"
                key={repo.url}
                className="recent-repo-chip"
                disabled={isUploading}
                onClick={() => onIndexRepo(repo.url)}
                title={repo.url}
              >
                <IGit /> {repo.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quick-start prompt chips */}
      <div className="welcome-chips">
        {CHIPS.map((chip) => (
          <button
            type="button"
            key={chip}
            className="welcome-chip"
            onClick={() => handleChipClick(chip)}
            disabled={isUploading}
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
