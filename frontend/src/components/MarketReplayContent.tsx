import React, { useState } from 'react';

interface MarketReplayResults {
  pnl: number;
  trades: number;
}

const MarketReplayContent: React.FC = () => {
  const [strategy, setStrategy] = useState<string>('orb');
  const [instrumentToken, setInstrumentToken] = useState<string>('');
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [results, setResults] = useState<MarketReplayResults | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setResults(null);

    const formData = {
      strategy,
      instrument: instrumentToken,
      'from-date': fromDate,
      'to-date': toDate,
    };

    try {
      const response = await fetch('http://localhost:8000/api/market_replay', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (response.ok) {
        setResults(data);
      } else {
        console.error('Market Replay failed:', data.message);
      }
    } catch (error) {
      console.error('Error during market replay:', error);
    }
  };

  return (
    <div className="container mt-4">
      <h2>Market Replay</h2>
      <form onSubmit={handleSubmit}>
        <div className="row">
          <div className="col-md-6 mb-3">
            <label htmlFor="replay-strategy" className="form-label">Strategy</label>
            <select
              className="form-select"
              id="replay-strategy"
              name="strategy"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              <option value="orb">Opening Range Breakout (ORB)</option>
            </select>
          </div>
          <div className="col-md-6 mb-3">
            <label htmlFor="replay-instrument" className="form-label">Instrument Token</label>
            <input
              type="text"
              className="form-control"
              id="replay-instrument"
              name="instrument"
              value={instrumentToken}
              onChange={(e) => setInstrumentToken(e.target.value)}
            />
          </div>
        </div>
        <div className="row">
          <div className="col-md-6 mb-3">
            <label htmlFor="replay-from-date" className="form-label">From Date</label>
            <input
              type="date"
              className="form-control"
              id="replay-from-date"
              name="from-date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
            />
          </div>
          <div className="col-md-6 mb-3">
            <label htmlFor="replay-to-date" className="form-label">To Date</label>
            <input
              type="date"
              className="form-control"
              id="replay-to-date"
              name="to-date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
            />
          </div>
        </div>
        <button type="submit" className="btn btn-primary">Start Replay</button>
      </form>
      {results && (
        <div className="mt-4">
          <h5>Market Replay Results</h5>
          <p>P&L: {results.pnl}</p>
          <p>Number of Trades: {results.trades}</p>
        </div>
      )}
    </div>
  );
};

export default MarketReplayContent;
