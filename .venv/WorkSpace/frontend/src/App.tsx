import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
import './App.css';

// LoginPage component
const LoginPage = () => {
  const handleLogin = () => {
    // Redirect to the backend to initiate Zerodha login
    window.location.href = 'http://localhost:8000/api/zerodha/login';
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Welcome to the Algorithmic Trading Platform</h1>
        <button onClick={handleLogin}>Login with Zerodha</button>
      </header>
    </div>
  );
};

// Define the type for the profile data
interface Profile {
  user_name: string;
  equity: {
    available: {
      margin: number;
    };
  };
}

// Props for ControlPanel
interface ControlPanelProps {
  strategy: string;
  setStrategy: (strategy: string) => void;
  candle: string;
  setCandle: (candle: string) => void;
  index: string;
  setIndex: (index: string) => void;
  startTime: string;
  setStartTime: (time: string) => void;
  targetProfit: number;
  setTargetProfit: (profit: number) => void;
  stopLoss: number;
  setStopLoss: (loss: number) => void;
  quantity: number;
  setQuantity: (quantity: number) => void;
  startStrategy: () => void;
  stopStrategy: () => void;
  tradeActive: boolean;
}

// ControlPanel component
const ControlPanel: React.FC<ControlPanelProps> = ({
  strategy,
  setStrategy,
  candle,
  setCandle,
  index,
  setIndex,
  startTime,
  setStartTime,
  targetProfit,
  setTargetProfit,
  stopLoss,
  setStopLoss,
  quantity,
  setQuantity,
  startStrategy,
  stopStrategy,
  tradeActive,
}) => {
  return (
    <div>
      <h2>Control Panel</h2>
      <div>
        <label>Strategy: </label>
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          <option value="orb">Open Range Breakout</option>
        </select>
      </div>
      <div>
        <label>Candle: </label>
        <select value={candle} onChange={(e) => setCandle(e.target.value)}>
          <option value="5min">5 Minutes</option>
        </select>
      </div>
      <div>
        <label>Index: </label>
        <select value={index} onChange={(e) => setIndex(e.target.value)}>
          <option value="NIFTY">Nifty</option>
          <option value="BANKNIFTY">Bank Nifty</option>
        </select>
      </div>
      <div>
        <label>Start Time: </label>
        <input
          type="time"
          value={startTime}
          onChange={(e) => setStartTime(e.target.value)}
        />
      </div>
      <div>
        <label>Target Profit: </label>
        <input
          type="number"
          value={targetProfit}
          onChange={(e) => setTargetProfit(parseInt(e.target.value))}
        />
      </div>
      <div>
        <label>Stop Loss: </label>
        <input
          type="number"
          value={stopLoss}
          onChange={(e) => setStopLoss(parseInt(e.target.value))}
        />
      </div>
      <div>
        <label>Quantity: </label>
        <input
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(parseInt(e.target.value))}
        />
      </div>
      {!tradeActive ? (
        <button onClick={startStrategy}>Start Strategy</button>
      ) : (
        <button onClick={stopStrategy}>Stop Strategy</button>
      )}
    </div>
  );
};

// Props for TradeMonitor
interface TradeMonitorProps {
  pnl: number;
  squareOff: () => void;
}

// TradeMonitor component
const TradeMonitor: React.FC<TradeMonitorProps> = ({ pnl, squareOff }) => {
  return (
    <div>
      <h2>Trade Monitor</h2>
      <p>Live P&L: {pnl}</p>
      <button onClick={squareOff}>Square Off</button>
    </div>
  );
};

// Dashboard component
const Dashboard = () => {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [strategy, setStrategy] = useState('orb');
  const [candle, setCandle] = useState('5min');
  const [index, setIndex] = useState('NIFTY');
  const [startTime, setStartTime] = useState('');
  const [targetProfit, setTargetProfit] = useState(0);
  const [stopLoss, setStopLoss] = useState(0);
  const [quantity, setQuantity] = useState(0);
  const [pnl, setPnl] = useState(0);
  const [tradeActive, setTradeActive] = useState(false);

  useEffect(() => {
    // Fetch user profile from the backend
    const fetchProfile = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/user/profile');
        const data = await response.json();
        setProfile(data);
      } catch (error) {
        console.error('Error fetching profile:', error);
      }
    };

    fetchProfile();
  }, []);

  const startStrategy = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/strategy/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategy,
          candle,
          index,
          startTime,
          targetProfit,
          stopLoss,
          quantity,
        }),
      });
      const data = await response.json();
      if (data.status === 'success') {
        setTradeActive(true);
      }
    } catch (error) {
      console.error('Error starting strategy:', error);
    }
  };

  const stopStrategy = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/strategy/stop', {
        method: 'POST',
      });
      const data = await response.json();
      if (data.status === 'success') {
        setTradeActive(false);
      }
    } catch (error) {
      console.error('Error stopping strategy:', error);
    }
  };

  const squareOff = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/trade/squareoff', {
        method: 'POST',
      });
      const data = await response.json();
      if (data.status === 'success') {
        setTradeActive(false);
      }
    } catch (error) {
      console.error('Error squaring off:', error);
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (tradeActive) {
      interval = setInterval(async () => {
        try {
          const response = await fetch('http://localhost:8000/api/trade/pnl');
          const data = await response.json();
          setPnl(data.pnl);
        } catch (error) {
          console.error('Error fetching P&L:', error);
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [tradeActive]);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Dashboard</h1>
        {profile ? (
          <div>
            <p>Welcome, {profile.user_name}!</p>
            {profile.equity && profile.equity.available ? (
              <p>Available Balance: {profile.equity.available.margin}</p>
            ) : (
              <p>Balance not available</p>
            )}
          </div>
        ) : (
          <p>Loading profile...</p>
        )}
        <Link to="/">Logout</Link>
      </header>
      <div className="App-body">
        <ControlPanel
          strategy={strategy}
          setStrategy={setStrategy}
          candle={candle}
          setCandle={setCandle}
          index={index}
          setIndex={setIndex}
          startTime={startTime}
          setStartTime={setStartTime}
          targetProfit={targetProfit}
          setTargetProfit={setTargetProfit}
          stopLoss={stopLoss}
          setStopLoss={setStopLoss}
          quantity={quantity}
          setQuantity={setQuantity}
          startStrategy={startStrategy}
          stopStrategy={stopStrategy}
          tradeActive={tradeActive}
        />
        {tradeActive && <TradeMonitor pnl={pnl} squareOff={squareOff} />}
      </div>
    </div>
  );
};

// App component with routing
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </Router>
  );
}

export default App;
