import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { io, Socket } from 'socket.io-client';

interface MarketReplayResults {
  pnl: number;
  trades: number;
  currentPrice?: number;
  currentTime?: string;
  progress?: number;
  status?: 'idle' | 'running' | 'paused' | 'completed' | 'error';
}

interface ReplayDataPoint {
  time: string;
  price: number;
  pnl: number;
}

const MarketReplayContent: React.FC = () => {
  const [strategy, setStrategy] = useState<string>('');
  const [instrumentToken, setInstrumentToken] = useState<string>('');
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [results, setResults] = useState<MarketReplayResults | null>(null);
  const [replayStatus, setReplayStatus] = useState<'idle' | 'running' | 'paused' | 'completed' | 'error'>('idle');
  const [speed, setSpeed] = useState<number>(1); // 0.5x, 1x, 2x, 5x, 10x
  const [progress, setProgress] = useState<number>(0);
  const [replayData, setReplayData] = useState<ReplayDataPoint[]>([]);
  const [currentTime, setCurrentTime] = useState<string>('');
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // Initialize socket connection
    socketRef.current = io('http://localhost:8000');
    
    const socket = socketRef.current;

    socket.on('connect', () => {
      console.log('Connected to WebSocket for market replay');
    });

    socket.on('replay_update', (data: {
      currentPrice: number;
      currentTime: string;
      pnl: number;
      progress: number;
      status: string;
    }) => {
      setCurrentPrice(data.currentPrice);
      setCurrentTime(data.currentTime);
      setProgress(data.progress);
      
      // Update replay data for chart
      setReplayData(prev => [...prev, {
        time: data.currentTime,
        price: data.currentPrice,
        pnl: data.pnl
      }]);

      // Update results
      setResults(prev => ({
        ...prev!,
        pnl: data.pnl,
        currentPrice: data.currentPrice,
        currentTime: data.currentTime,
        progress: data.progress,
      }));
    });

    socket.on('replay_complete', (data: { pnl: number; trades: number }) => {
      setReplayStatus('completed');
      setResults(prev => ({
        ...prev!,
        pnl: data.pnl,
        trades: data.trades,
        status: 'completed',
      }));
    });

    socket.on('replay_error', (data: { message: string }) => {
      setReplayStatus('error');
      console.error('Replay error:', data.message);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const handleStartReplay = async () => {
    if (!strategy || !instrumentToken || !fromDate || !toDate) {
      alert('Please fill in all fields');
      return;
    }

    setReplayStatus('running');
    setProgress(0);
    setReplayData([]);
    setResults({
      pnl: 0,
      trades: 0,
      status: 'running',
    });

    const formData = {
      strategy,
      instrument: instrumentToken,
      'from-date': fromDate,
      'to-date': toDate,
      speed: speed,
    };

    try {
      const response = await fetch('http://localhost:8000/api/market_replay', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (!response.ok) {
        setReplayStatus('error');
        alert(data.message || 'Market Replay failed');
      }
    } catch (error) {
      console.error('Error starting market replay:', error);
      setReplayStatus('error');
      alert('An error occurred while starting market replay');
    }
  };

  const handlePause = () => {
    if (socketRef.current) {
      socketRef.current.emit('replay_pause');
      setReplayStatus('paused');
    }
  };

  const handleResume = () => {
    if (socketRef.current) {
      socketRef.current.emit('replay_resume', { speed });
      setReplayStatus('running');
    }
  };

  const handleStop = () => {
    if (socketRef.current) {
      socketRef.current.emit('replay_stop');
      setReplayStatus('idle');
      setReplayData([]);
      setResults(null);
      setProgress(0);
    }
  };

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed);
    if (replayStatus === 'running' && socketRef.current) {
      socketRef.current.emit('replay_speed_change', { speed: newSpeed });
    }
  };

  const speedOptions = [
    { value: 0.5, label: '0.5x' },
    { value: 1, label: '1x' },
    { value: 2, label: '2x' },
    { value: 5, label: '5x' },
    { value: 10, label: '10x' },
  ];

  return (
    <div className="container mt-4">
      <div className="card shadow-sm border-0">
        <div className="card-header bg-success text-white">
          <h5 className="card-title mb-0">
            <i className="bi bi-play-circle me-2"></i>Market Replay
          </h5>
        </div>
        <div className="card-body">
          <form onSubmit={(e) => { e.preventDefault(); handleStartReplay(); }}>
            <div className="row mb-3">
              <div className="col-md-6 mb-3">
                <label htmlFor="replay-strategy" className="form-label">
                  <i className="bi bi-diagram-3 me-2"></i>Strategy
                </label>
                <input
                  type="text"
                  className="form-control"
                  id="replay-strategy"
                  name="strategy"
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                  placeholder="Strategy ID"
                  required
                />
                <small className="text-muted">Enter the strategy ID to replay</small>
              </div>
              <div className="col-md-6 mb-3">
                <label htmlFor="replay-instrument" className="form-label">
                  <i className="bi bi-graph-up me-2"></i>Instrument Token
                </label>
                <input
                  type="text"
                  className="form-control"
                  id="replay-instrument"
                  name="instrument"
                  value={instrumentToken}
                  onChange={(e) => setInstrumentToken(e.target.value)}
                  placeholder="Instrument Token"
                  required
                />
              </div>
            </div>
            <div className="row mb-3">
              <div className="col-md-6 mb-3">
                <label htmlFor="replay-from-date" className="form-label">
                  <i className="bi bi-calendar3 me-2"></i>From Date
                </label>
                <input
                  type="date"
                  className="form-control"
                  id="replay-from-date"
                  name="from-date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                  required
                />
              </div>
              <div className="col-md-6 mb-3">
                <label htmlFor="replay-to-date" className="form-label">
                  <i className="bi bi-calendar3 me-2"></i>To Date
                </label>
                <input
                  type="date"
                  className="form-control"
                  id="replay-to-date"
                  name="to-date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Speed Controls */}
            <div className="row mb-3">
              <div className="col-md-12">
                <label className="form-label">
                  <i className="bi bi-speedometer2 me-2"></i>Playback Speed
                </label>
                <div className="btn-group w-100" role="group">
                  {speedOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`btn ${speed === option.value ? 'btn-primary' : 'btn-outline-primary'}`}
                      onClick={() => handleSpeedChange(option.value)}
                      disabled={replayStatus === 'idle'}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Control Buttons */}
            <div className="row mb-3">
              <div className="col-md-12">
                <div className="btn-group" role="group">
                  {replayStatus === 'idle' && (
                    <button type="submit" className="btn btn-success">
                      <i className="bi bi-play-fill me-2"></i>Start Replay
                    </button>
                  )}
                  {replayStatus === 'running' && (
                    <>
                      <button type="button" className="btn btn-warning" onClick={handlePause}>
                        <i className="bi bi-pause-fill me-2"></i>Pause
                      </button>
                      <button type="button" className="btn btn-danger" onClick={handleStop}>
                        <i className="bi bi-stop-fill me-2"></i>Stop
                      </button>
                    </>
                  )}
                  {replayStatus === 'paused' && (
                    <>
                      <button type="button" className="btn btn-success" onClick={handleResume}>
                        <i className="bi bi-play-fill me-2"></i>Resume
                      </button>
                      <button type="button" className="btn btn-danger" onClick={handleStop}>
                        <i className="bi bi-stop-fill me-2"></i>Stop
                      </button>
                    </>
                  )}
                  {replayStatus === 'completed' && (
                    <button type="button" className="btn btn-primary" onClick={handleStop}>
                      <i className="bi bi-arrow-clockwise me-2"></i>Reset
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            {(replayStatus === 'running' || replayStatus === 'paused' || replayStatus === 'completed') && (
              <div className="row mb-3">
                <div className="col-md-12">
                  <label className="form-label">Progress</label>
                  <div className="progress" style={{ height: '25px' }}>
                    <div
                      className={`progress-bar ${
                        replayStatus === 'completed' ? 'bg-success' :
                        replayStatus === 'paused' ? 'bg-warning' :
                        'bg-info progress-bar-striped progress-bar-animated'
                      }`}
                      role="progressbar"
                      style={{ width: `${progress}%` }}
                      aria-valuenow={progress}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      {progress.toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Current Status Display */}
            {(replayStatus === 'running' || replayStatus === 'paused' || replayStatus === 'completed') && (
              <div className="row mb-3">
                <div className="col-md-4">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <small className="text-muted d-block">Current Price</small>
                      <h5 className="mb-0 fw-bold text-primary">{currentPrice.toFixed(2)}</h5>
                    </div>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <small className="text-muted d-block">Current Time</small>
                      <h6 className="mb-0">{currentTime || '--'}</h6>
                    </div>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <small className="text-muted d-block">Current P&L</small>
                      <h5 className={`mb-0 fw-bold ${(results?.pnl || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                        {(results?.pnl || 0).toFixed(2)}
                      </h5>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </form>

          {/* Results Display */}
          {results && replayStatus === 'completed' && (
            <div className="mt-4">
              <div className="card bg-light">
                <div className="card-header">
                  <h5 className="mb-0">
                    <i className="bi bi-check-circle-fill text-success me-2"></i>Market Replay Results
                  </h5>
                </div>
                <div className="card-body">
                  <div className="row">
                    <div className="col-md-6">
                      <p className="mb-2">
                        <strong>Total P&L:</strong>{' '}
                        <span className={results.pnl >= 0 ? 'text-success' : 'text-danger'}>
                          {results.pnl.toFixed(2)}
                        </span>
                      </p>
                    </div>
                    <div className="col-md-6">
                      <p className="mb-2">
                        <strong>Number of Trades:</strong> {results.trades}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Chart Visualization */}
          {replayData.length > 0 && (
            <div className="mt-4">
              <div className="card">
                <div className="card-header">
                  <h5 className="mb-0">
                    <i className="bi bi-graph-up me-2"></i>Replay Chart
                  </h5>
                </div>
                <div className="card-body">
                  <div style={{ height: '400px', width: '100%' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={replayData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                        <XAxis
                          dataKey="time"
                          stroke="#666"
                          style={{ fontSize: '12px' }}
                        />
                        <YAxis
                          stroke="#666"
                          style={{ fontSize: '12px' }}
                          yAxisId="left"
                        />
                        <YAxis
                          stroke="#666"
                          style={{ fontSize: '12px' }}
                          yAxisId="right"
                          orientation="right"
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#fff',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                          }}
                        />
                        <Legend />
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="price"
                          stroke="#0d6efd"
                          strokeWidth={2}
                          dot={false}
                          name="Price"
                          activeDot={{ r: 4 }}
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="pnl"
                          stroke="#28a745"
                          strokeWidth={2}
                          dot={false}
                          name="P&L"
                          activeDot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MarketReplayContent;
