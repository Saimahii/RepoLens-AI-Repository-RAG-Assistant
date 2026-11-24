import '../styles/Sidebar.css';
import {
  ILens,
  IHome,
  IChat,
  IHistory,
  IGit,
  IFolder,
  ISettings,
  ISun,
  IMoon,
} from '../utils/icons';

// Left icon-rail navigation — every button is wired to a real action or slide-out drawer
export default function Sidebar({
  activeNav,
  openDrawer,
  onSelectNav,
  theme,
  onToggleTheme,
  sessionCount,
  repoCount,
}) {
  const navItems = [
    { id: 'home', icon: IHome, label: 'Home / Connect Repo' },
    { id: 'chat', icon: IChat, label: 'Chat Workspace' },
    { id: 'history', icon: IHistory, label: 'Chat History', badge: sessionCount },
    { id: 'repos', icon: IGit, label: 'Repositories', badge: repoCount },
    { id: 'files', icon: IFolder, label: 'File Explorer' },
  ];

  const isHighlighted = (id) => {
    if (openDrawer) return openDrawer === id;
    return activeNav === id;
  };

  return (
    <div className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo" onClick={() => onSelectNav('home')} title="RepoLens — Home">
        <ILens />
      </div>

      {/* Main nav icons */}
      <div className="sidebar-nav">
        {navItems.map((item) => (
          <button
            type="button"
            key={item.id}
            className={`sidebar-btn ${isHighlighted(item.id) ? 'active' : ''}`}
            onClick={() => onSelectNav(item.id)}
            title={item.label}
          >
            <item.icon />
            {item.badge > 0 && <span className="sidebar-badge">{item.badge > 9 ? '9+' : item.badge}</span>}
          </button>
        ))}
      </div>

      {/* Bottom theme toggle, settings, and avatar */}
      <div className="sidebar-bottom">
        <button
          type="button"
          className="sidebar-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? <ISun /> : <IMoon />}
        </button>
        <button
          type="button"
          className={`sidebar-btn ${openDrawer === 'settings' ? 'active' : ''}`}
          onClick={() => onSelectNav('settings')}
          title="Settings"
        >
          <ISettings />
        </button>
        <div
          className="sidebar-avatar"
          onClick={() => onSelectNav('settings')}
          title="RepoLens Workspace"
        >
          RL
        </div>
      </div>
    </div>
  );
}
