import React from 'react';

interface NavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  userName: string;
  onLogout: () => void;
}

const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange, userName, onLogout }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'backtest', label: 'Backtest', icon: '🔍' },
    { id: 'market-replay', label: 'Market Replay', icon: '📈' },
    { id: 'tick-data', label: 'Tick Data', icon: '📉' },
  ];

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-dark shadow-sm">
      <div className="container-fluid">
        <a className="navbar-brand d-flex align-items-center" href="/">
          <span className="fs-4 fw-bold text-primary">ZerodhaKite</span>
        </a>
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarNav"
          aria-controls="navbarNav"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="navbar-toggler-icon"></span>
        </button>
        <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav me-auto mb-2 mb-lg-0">
            {navItems.map((item) => (
              <li key={item.id} className="nav-item">
                <button
                  className={`nav-link ${activeTab === item.id ? 'active fw-bold' : ''}`}
                  onClick={() => onTabChange(item.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: activeTab === item.id ? '#0d6efd' : 'rgba(255,255,255,.55)',
                    cursor: 'pointer',
                    padding: '0.5rem 1rem',
                  }}
                  onMouseEnter={(e) => {
                    if (activeTab !== item.id) {
                      e.currentTarget.style.color = '#fff';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (activeTab !== item.id) {
                      e.currentTarget.style.color = 'rgba(255,255,255,.55)';
                    }
                  }}
                >
                  <span className="me-2">{item.icon}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
          <ul className="navbar-nav ms-auto">
            <li className="nav-item">
              <span className="nav-link text-light">
                <i className="bi bi-person-circle me-2"></i>
                Welcome, <strong>{userName}</strong>
              </span>
            </li>
            <li className="nav-item">
              <button
                className="nav-link btn btn-link text-light text-decoration-none"
                onClick={onLogout}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '0.5rem 1rem',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#0d6efd';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#fff';
                }}
              >
                <i className="bi bi-box-arrow-right me-1"></i>
                Logout
              </button>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;

