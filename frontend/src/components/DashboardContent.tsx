import React, { useState, useEffect } from 'react';

// Enhanced Market Data Component
const MarketData: React.FC<{ niftyPrice: string; bankNiftyPrice: string }> = ({ niftyPrice, bankNiftyPrice }) => (
  <div className="card shadow-sm border-0 mb-4">
    <div className="card-header bg-primary text-white">
      <h5 className="card-title mb-0">
        <i className="bi bi-graph-up-arrow me-2"></i>Live Market Data
      </h5>
    </div>
    <div className="card-body">
      <div className="row g-3">
        <div className="col-md-6">
          <div className="d-flex align-items-center p-3 bg-light rounded">
            <div className="flex-grow-1">
              <small className="text-muted d-block">NIFTY 50</small>
              <h4 className="mb-0 fw-bold text-primary" id="nifty-price">{niftyPrice}</h4>
            </div>
            <div className="ms-3">
              <span className="badge bg-success fs-6">LIVE</span>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="d-flex align-items-center p-3 bg-light rounded">
            <div className="flex-grow-1">
              <small className="text-muted d-block">BANK NIFTY</small>
              <h4 className="mb-0 fw-bold text-info" id="banknifty-price">{bankNiftyPrice}</h4>
            </div>
            <div className="ms-3">
              <span className="badge bg-success fs-6">LIVE</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// Enhanced Account Info Component
const AccountInfo: React.FC<{ balance: string; access_token: boolean }> = ({ balance, access_token }) => (
  <div className="card shadow-sm border-0 mb-4">
    <div className="card-header bg-success text-white">
      <h5 className="card-title mb-0">
        <i className="bi bi-wallet2 me-2"></i>Account Information
      </h5>
    </div>
    <div className="card-body">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <span className="text-muted">Available Balance:</span>
        <h4 className="mb-0 fw-bold text-success" id="balance">₹{balance}</h4>
      </div>
      {!access_token && (
        <a href="http://localhost:8000/zerodha_login" className="btn btn-primary w-100">
          <i className="bi bi-box-arrow-in-right me-2"></i>Connect with Zerodha
        </a>
      )}
    </div>
  </div>
);

const StrategyConfiguration: React.FC<{ onStrategySaved: () => void }> = ({ onStrategySaved }) => {
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [strategyName, setStrategyName] = useState<string>('');
  const [emaPeriod, setEmaPeriod] = useState<number>(5);
  const [segment, setSegment] = useState<string>('Option');
  const [totalLot, setTotalLot] = useState<number>(1);
  const [tradeType, setTradeType] = useState<string>('Buy');
  const [strikePrice, setStrikePrice] = useState<string>('ATM');
  const [expiryType, setExpiryType] = useState<string>('Weekly');
  const [instrument, setInstrument] = useState<string>('NIFTY');
  const [candleTime, setCandleTime] = useState<string>('5');
  const [executionStart, setExecutionStart] = useState<string>('09:15');
  const [executionEnd, setExecutionEnd] = useState<string>('15:00');
  const [stopLoss, setStopLoss] = useState<number>(1);
  const [targetProfit, setTargetProfit] = useState<number>(2);
  const [trailingStopLoss, setTrailingStopLoss] = useState<number>(0.5);
  const [paperTrade, setPaperTrade] = useState<boolean>(false);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const strategyDescriptions: { [key: string]: string } = {
    'orb': `
      <h5>Opening Range Breakout (ORB)</h5>
      <p>This strategy identifies the high and low of the opening range and places a trade when the price breaks out of this range.</p>
      <strong>Timeframe:</strong> Configurable (e.g., 15 minutes)<br>
      <strong>Instruments:</strong> Nifty & BankNifty<br>
      <strong>Logic:</strong><br>
      <ul>
          <li><strong>Opening Range:</strong> The high and low of the first 'x' minutes of the trading session.</li>
          <li><strong>Buy Signal:</strong> Price breaks above the opening range high.</li>
          <li><strong>Sell Signal:</strong> Price breaks below the opening range low.</li>
          <li><strong>Stop Loss & Target:</strong> Configurable percentages.</li>
      </ul>
    `,
    'capture_mountain_signal': `
      <h5>Capture Mountain Signal</h5>
      <p><strong>Instruments:</strong> Nifty & BankNifty ATM Options</p>
      <p><strong>Timeframe:</strong> 5-minute candles</p>
      <p><strong>Indicator:</strong> 5-period EMA</p>
      <h6>PE (Put Entry) Logic</h6>
      <ul>
          <li><strong>Signal Candle:</strong> Candle's LOW > 5 EMA</li>
          <li><strong>Entry Trigger:</strong> Next candle CLOSE < signal candle's LOW</li>
          <li><strong>Stop Loss:</strong> Price closes above signal candle's HIGH</li>
          <li><strong>Target:</strong> Wait for at least 1 candle where HIGH < 5 EMA, then if 2 consecutive candles CLOSE > 5 EMA -> Exit PE trade</li>
      </ul>
      <h6>CE (Call Entry) Logic</h6>
      <ul>
          <li><strong>Signal Candle:</strong> Candle's HIGH < 5 EMA</li>
          <li><strong>Entry Trigger:</strong> Next candle CLOSE > signal candle's HIGH</li>
          <li><strong>Stop Loss:</strong> Price closes below signal candle's LOW</li>
          <li><strong>Target:</strong> Wait for at least 1 candle where LOW > 5 EMA, then if 2 consecutive candles CLOSE < 5 EMA -> Exit CE trade</li>
      </ul>
    `,
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);

    const formData = {
      strategy: selectedStrategy,
      'strategy-name': strategyName,
      'ema-period': emaPeriod,
      segment,
      'total-lot': totalLot,
      'trade-type': tradeType,
      'strike-price': strikePrice,
      'expiry-type': expiryType,
      instrument,
      'candle-time': candleTime,
      'execution-start': executionStart,
      'execution-end': executionEnd,
      'stop-loss': stopLoss,
      'target-profit': targetProfit,
      'trailing-stop-loss': trailingStopLoss,
      paper_trade: paperTrade,
    };

    try {
      const response = await fetch('http://localhost:8000/api/strategy/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ type: 'success', text: data.message || 'Strategy saved successfully!' });
        onStrategySaved(); // Callback to refresh saved strategies
        // Optionally reset form
      } else {
        setMessage({ type: 'danger', text: data.message || 'Failed to save strategy.' });
      }
    } catch (error) {
      console.error('Error saving strategy:', error);
      setMessage({ type: 'danger', text: 'An error occurred. Please try again.' });
    }
  };

  return (
    <div className="accordion-item">
      <h2 className="accordion-header" id="headingOne">
        <button
          className="accordion-button"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#collapseOne"
          aria-expanded="true"
          aria-controls="collapseOne"
        >
          Strategy Configuration
        </button>
      </h2>
      <div id="collapseOne" className="accordion-collapse collapse show" aria-labelledby="headingOne" data-bs-parent="#dashboardAccordion">
        <div className="accordion-body">
          <div className="mb-3">
            <label htmlFor="strategy-select" className="form-label">Select Strategy</label>
            <select
              className="form-select"
              id="strategy-select"
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
            >
              <option value="" disabled>Select Strategy</option>
              <option value="orb">Opening Range Breakout (ORB)</option>
              <option value="capture_mountain_signal">Capture Mountain Signal</option>
            </select>
          </div>
          <div
            id="strategy-description"
            className="alert alert-info"
            dangerouslySetInnerHTML={{ __html: strategyDescriptions[selectedStrategy] || '' }}
          ></div>
          <div id="orb-strategy-form">
            {message && (
              <div className={`alert alert-${message.type}`}>
                {message.text}
              </div>
            )}
            <form onSubmit={handleSubmit}>
              <input type="hidden" name="strategy" id="strategy-input" value={selectedStrategy} />
              <input type="hidden" name="strategy_id" id="strategy-id" />
              <div className="row">
                <div className="col-md-12 mb-3">
                  <label htmlFor="strategy-name" className="form-label">Strategy Name</label>
                  <input
                    type="text"
                    className="form-control"
                    id="strategy-name"
                    name="strategy-name"
                    value={strategyName}
                    onChange={(e) => setStrategyName(e.target.value)}
                    required
                  />
                </div>
              </div>
              {selectedStrategy === 'capture_mountain_signal' && (
                <div className="row">
                  <div className="col-md-12 mb-3">
                    <label htmlFor="ema-period" className="form-label">EMA Period</label>
                    <input
                      type="number"
                      className="form-control"
                      id="ema-period"
                      name="ema-period"
                      value={emaPeriod}
                      onChange={(e) => setEmaPeriod(Number(e.target.value))}
                    />
                  </div>
                </div>
              )}
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="segment" className="form-label">Select Segment</label>
                  <select
                    className="form-select"
                    id="segment"
                    name="segment"
                    value={segment}
                    onChange={(e) => setSegment(e.target.value)}
                    disabled
                  >
                    <option value="Option">Option</option>
                    <option value="Future">Future</option>
                  </select>
                </div>
                <div className="col-md-6 mb-3">
                  <label htmlFor="total-lot" className="form-label">Total Lot</label>
                  <input
                    type="number"
                    className="form-control"
                    id="total-lot"
                    name="total-lot"
                    min={1}
                    max={50}
                    value={totalLot}
                    onChange={(e) => setTotalLot(Number(e.target.value))}
                    required
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="trade-type" className="form-label">Buy or Sell</label>
                  <select
                    className="form-select"
                    id="trade-type"
                    name="trade-type"
                    value={tradeType}
                    onChange={(e) => setTradeType(e.target.value)}
                    disabled
                  >
                    <option value="Buy">Buy</option>
                    <option value="Sell">Sell</option>
                  </select>
                </div>
                <div className="col-md-6 mb-3">
                  <label htmlFor="strike-price" className="form-label">Strike Price</label>
                  <input
                    type="text"
                    className="form-control"
                    id="strike-price"
                    name="strike-price"
                    value={strikePrice}
                    onChange={(e) => setStrikePrice(e.target.value)}
                    readOnly
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="expiry-type" className="form-label">Expiry Type</label>
                  <select
                    className="form-select"
                    id="expiry-type"
                    name="expiry-type"
                    value={expiryType}
                    onChange={(e) => setExpiryType(e.target.value)}
                  >
                    <option value="Weekly">Weekly</option>
                    <option value="Next Weekly">Next Weekly</option>
                    <option value="Monthly">Monthly</option>
                  </select>
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="instrument" className="form-label">Instrument</label>
                  <select
                    className="form-select"
                    id="instrument"
                    name="instrument"
                    value={instrument}
                    onChange={(e) => setInstrument(e.target.value)}
                  >
                    <option value="NIFTY">NIFTY</option>
                    <option value="BANKNIFTY">BANKNIFTY</option>
                  </select>
                </div>
                <div className="col-md-6 mb-3">
                  <label htmlFor="candle-time" className="form-label">Candle Time</label>
                  <select
                    className="form-select"
                    id="candle-time"
                    name="candle-time"
                    value={candleTime}
                    onChange={(e) => setCandleTime(e.target.value)}
                  >
                    <option value="5">5 minutes</option>
                    <option value="10">10 minutes</option>
                    <option value="15">15 minutes</option>
                  </select>
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="execution-start" className="form-label">Execution Start</label>
                  <input
                    type="time"
                    className="form-control"
                    id="execution-start"
                    name="execution-start"
                    value={executionStart}
                    onChange={(e) => setExecutionStart(e.target.value)}
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label htmlFor="execution-end" className="form-label">Execution End</label>
                  <input
                    type="time"
                    className="form-control"
                    id="execution-end"
                    name="execution-end"
                    value={executionEnd}
                    onChange={(e) => setExecutionEnd(e.target.value)}
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="stop-loss" className="form-label">Stop Loss (%)</label>
                  <input
                    type="number"
                    className="form-control"
                    id="stop-loss"
                    name="stop-loss"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(Number(e.target.value))}
                  />
                </div>
                <div className="col-md-6 mb-3">
                  <label htmlFor="target-profit" className="form-label">Target Profit (%)</label>
                  <input
                    type="number"
                    className="form-control"
                    id="target-profit"
                    name="target-profit"
                    value={targetProfit}
                    onChange={(e) => setTargetProfit(Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="row">
                <div className="col-md-6 mb-3">
                  <label htmlFor="trailing-stop-loss" className="form-label">Trailing Stop Loss (%)</label>
                  <input
                    type="number"
                    className="form-control"
                    id="trailing-stop-loss"
                    name="trailing-stop-loss"
                    value={trailingStopLoss}
                    onChange={(e) => setTrailingStopLoss(Number(e.target.value))}
                  />
                </div>
                <div className="col-md-6 mb-3 form-check mt-4">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    id="paper-trade"
                    name="paper_trade"
                    checked={paperTrade}
                    onChange={(e) => setPaperTrade(e.target.checked)}
                  />
                  <label className="form-check-label" htmlFor="paper-trade">Paper Trade</label>
                </div>
              </div>
              <button type="submit" className="btn btn-primary">Save Strategy</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

interface Strategy {
  id: string;
  strategy_name: string;
  instrument: string;
  expiry_type: string;
  total_lot: number;
  status: string;
  // Add other strategy properties as needed
}

interface SavedStrategiesProps {
  onViewLive: (strategyId: string) => void;
  onStrategyUpdated: number;
}

const SavedStrategies: React.FC<SavedStrategiesProps> = ({ onViewLive, onStrategyUpdated }) => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);

  const fetchStrategies = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/strategies', { credentials: 'include' });
      const data = await response.json();
      if (data.status === 'success') {
        setStrategies(data.strategies);
      } else {
        console.error('Error fetching strategies:', data.message);
      }
    } catch (error) {
      console.error('Error fetching strategies:', error);
    }
  };

  useEffect(() => {
    fetchStrategies();
  }, [onStrategyUpdated]); // Re-fetch when onStrategyUpdated is called

  const handleEditStrategy = (strategyId: string) => {
    console.log('Edit strategy:', strategyId);
    // Implement edit logic, e.g., populate form with strategy data
  };

  const handleDeleteStrategy = async (strategyId: string) => {
    if (!window.confirm('Are you sure you want to delete this strategy?')) {
      return;
    }
    try {
      const response = await fetch(`http://localhost:8000/api/strategy/delete/${strategyId}`, { method: 'POST', credentials: 'include' });
      const data = await response.json();
      if (response.ok) {
        alert(data.message);
        fetchStrategies();
      } else {
        alert('Error: ' + data.message);
      }
    } catch (error) {
      console.error('Error deleting strategy:', error);
      alert('An error occurred while deleting the strategy.');
    }
  };

  const handleDeployStrategy = async (strategyId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/strategy/deploy/${strategyId}`, { method: 'POST', credentials: 'include' });
      const data = await response.json();
      if (response.ok) {
        alert(data.message);
        fetchStrategies();
      } else {
        alert('Error: ' + data.message);
      }
    } catch (error) {
      console.error('Error deploying strategy:', error);
      alert('An error occurred while deploying the strategy.');
    }
  };

  const handlePauseStrategy = async (strategyId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/strategy/pause/${strategyId}`, { method: 'POST', credentials: 'include' });
      const data = await response.json();
      if (response.ok) {
        alert(data.message);
        fetchStrategies();
      } else {
        alert('Error: ' + data.message);
      }
    } catch (error) {
      console.error('Error pausing strategy:', error);
      alert('An error occurred while pausing the strategy.');
    }
  };

  const handleSquareOffStrategy = async (strategyId: string) => {
    if (!window.confirm('Are you sure you want to square off this strategy?')) {
      return;
    }
    try {
      const response = await fetch(`http://localhost:8000/api/strategy/squareoff/${strategyId}`, { method: 'POST', credentials: 'include' });
      const data = await response.json();
      if (response.ok) {
        alert(data.message);
        fetchStrategies();
      } else {
        alert('Error: ' + data.message);
      }
    } catch (error) {
      console.error('Error squaring off strategy:', error);
      alert('An error occurred while squaring off the strategy.');
    }
  };

  return (
    <div className="accordion-item mt-3">
      <h2 className="accordion-header" id="headingTwo">
        <button
          className="accordion-button collapsed"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#collapseTwo"
          aria-expanded="false"
          aria-controls="collapseTwo"
        >
          Saved Strategies
        </button>
      </h2>
      <div id="collapseTwo" className="accordion-collapse collapse" aria-labelledby="headingTwo" data-bs-parent="#dashboardAccordion">
        <div className="accordion-body">
          <table className="table table-striped">
            <thead>
              <tr>
                <th>Name</th>
                <th>Instrument</th>
                <th>Expiry</th>
                <th>Lots</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody id="saved-strategies-table-body">
              {strategies.length === 0 ? (
                <tr>
                  <td colSpan={6}>No strategies saved yet.</td>
                </tr>
              ) : (
                strategies.map((strategy) => (
                  <tr key={strategy.id}>
                    <td>{strategy.strategy_name}</td>
                    <td>{strategy.instrument}</td>
                    <td>{strategy.expiry_type}</td>
                    <td>{strategy.total_lot}</td>
                    <td>{strategy.status}</td>
                    <td>
                      <button className="btn btn-sm btn-info" onClick={() => handleEditStrategy(strategy.id)}>Edit</button>
                      <button className="btn btn-sm btn-danger" onClick={() => handleDeleteStrategy(strategy.id)}>Delete</button>
                      {(strategy.status === 'saved' || strategy.status === 'paused' || strategy.status === 'error' || strategy.status === 'sq_off') && (
                        <button className="btn btn-sm btn-success" onClick={() => handleDeployStrategy(strategy.id)}>Deploy</button>
                      )}
                      {strategy.status === 'running' && (
                        <>
                          <button className="btn btn-sm btn-warning" onClick={() => handlePauseStrategy(strategy.id)}>Pause</button>
                          <button className="btn btn-sm btn-danger" onClick={() => handleSquareOffStrategy(strategy.id)}>Square Off</button>
                          <button className="btn btn-sm btn-primary" onClick={() => onViewLive(strategy.id)}>View Live</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const LivePnL: React.FC<{ pnl: number }> = ({ pnl }) => (
  <div className="card mt-3">
    <div className="card-body">
      <h5 className="card-title">Live P&L</h5>
      <p className="card-text">P&L: <span id="pnl">{pnl.toFixed(2)}</span></p>
    </div>
  </div>
);

const ActiveTrade: React.FC = () => {
  const showSquareOff = false; // This state should be managed by actual trade data

  const handleSquareOff = () => {
    console.log('Square Off active trade');
    // Implement API call to square off active trade
  };

  return (
    <div className="card mt-3">
      <div className="card-body">
        <h5 className="card-title">Active Trade</h5>
        {showSquareOff && (
          <button id="square-off-btn" className="btn btn-danger" onClick={handleSquareOff}>Square Off</button>
        )}
      </div>
    </div>
  );
};

const RunningStrategies: React.FC = () => {
  const [runningStrategies, setRunningStrategies] = useState<any[]>([]); // Define a proper interface for running strategies

  useEffect(() => {
    // Fetch running strategies from API
    const fetchRunningStrategies = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/running-strategies', { credentials: 'include' }); // Assuming an API endpoint for running strategies
        const data = await response.json();
        if (response.ok) {
          setRunningStrategies(data.strategies);
        } else {
          console.error('Error fetching running strategies:', data.message);
        }
      } catch (error) {
        console.error('Error fetching running strategies:', error);
      }
    };
    fetchRunningStrategies();
    const interval = setInterval(fetchRunningStrategies, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="card mt-3">
      <div className="card-body">
        <h5 className="card-title">Running Strategies</h5>
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Instrument</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="running-strategies">
            {runningStrategies.length === 0 ? (
              <tr>
                <td colSpan={5}>No strategies running.</td>
              </tr>
            ) : (
              runningStrategies.map((strategy) => (
                <tr key={strategy.id}>
                  <td>{strategy.id}</td>
                  <td>{strategy.strategy_name}</td>
                  <td>{strategy.instrument}</td>
                  <td>{strategy.status}</td>
                  <td>
                    {/* Add actions for running strategies if any */}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

interface DashboardContentProps {
  niftyPrice: string;
  bankNiftyPrice: string;
  balance: string;
  access_token: boolean;
  onViewLiveStrategy: (strategyId: string) => void;
  onViewChart: (instrumentToken: string) => void;
}

const DashboardContent: React.FC<DashboardContentProps> = ({ niftyPrice, bankNiftyPrice, balance, access_token, onViewLiveStrategy, onViewChart }) => {
  const [refreshStrategies, setRefreshStrategies] = useState<number>(0);

  const handleStrategySaved = () => {
    setRefreshStrategies(prev => prev + 1);
  };

  return (
    <div className="container mt-4" id="dashboard-content">
      <div className="row">
        <div className="col-md-4">
          <MarketData niftyPrice={niftyPrice} bankNiftyPrice={bankNiftyPrice} />
          <AccountInfo balance={balance} access_token={access_token} />
        </div>
        <div className="col-md-8">
          <div className="accordion" id="dashboardAccordion">
            <StrategyConfiguration onStrategySaved={handleStrategySaved} />
            <SavedStrategies onViewLive={onViewLiveStrategy} onStrategyUpdated={refreshStrategies} />
          </div>
          <LivePnL pnl={0} /> {/* P&L will be updated via WebSocket or API */}
          <ActiveTrade />
          <RunningStrategies />
        </div>
      </div>
    </div>
  );
};

export default DashboardContent;
