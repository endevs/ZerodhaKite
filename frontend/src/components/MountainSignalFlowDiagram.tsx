import React from 'react';

interface MountainSignalFlowDiagramProps {
  strategy: {
    strategy_type: string;
    instrument: string;
    candle_time: string;
    ema_period?: number;
  };
}

const MountainSignalFlowDiagram: React.FC<MountainSignalFlowDiagramProps> = ({ strategy }) => {
  const emaPeriod = strategy.ema_period || 5;
  const candleTime = strategy.candle_time || '5m';

  return (
    <div className="mountain-signal-flow-diagram" style={{ fontFamily: 'Arial, sans-serif' }}>
      <style>{`
        .mountain-signal-flow-diagram .flow-container {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          padding: 20px;
          border-radius: 10px;
          margin-bottom: 20px;
        }
        .mountain-signal-flow-diagram .flow-box {
          background: white;
          border: 2px solid #333;
          border-radius: 8px;
          padding: 15px;
          margin: 10px;
          box-shadow: 0 4px 6px rgba(0,0,0,0.1);
          position: relative;
          word-wrap: break-word;
        }
        .mountain-signal-flow-diagram .flow-box.start {
          background: #28a745;
          color: white;
          text-align: center;
          font-weight: bold;
        }
        .mountain-signal-flow-diagram .flow-box.decision {
          background: #ffc107;
          border-color: #ff9800;
          text-align: center;
          font-weight: bold;
          border-radius: 50px;
          min-width: 150px;
        }
        .mountain-signal-flow-diagram .flow-box.process {
          background: #17a2b8;
          color: white;
        }
        .mountain-signal-flow-diagram .flow-box.signal {
          background: #6f42c1;
          color: white;
        }
        .mountain-signal-flow-diagram .flow-box.entry {
          background: #28a745;
          color: white;
          font-weight: bold;
        }
        .mountain-signal-flow-diagram .flow-box.exit {
          background: #dc3545;
          color: white;
          font-weight: bold;
        }
        .mountain-signal-flow-diagram .flow-arrow {
          text-align: center;
          font-size: 24px;
          color: #333;
          margin: 5px 0;
        }
        .mountain-signal-flow-diagram .flow-row {
          display: flex;
          justify-content: center;
          align-items: flex-start;
          flex-wrap: wrap;
          margin: 10px 0;
        }
        .mountain-signal-flow-diagram .flow-column {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin: 0 10px;
        }
        .mountain-signal-flow-diagram .label-yes {
          color: #28a745;
          font-weight: bold;
          font-size: 12px;
        }
        .mountain-signal-flow-diagram .label-no {
          color: #dc3545;
          font-weight: bold;
          font-size: 12px;
        }
        .mountain-signal-flow-diagram .section-title {
          background: #343a40;
          color: white;
          padding: 10px;
          border-radius: 5px;
          text-align: center;
          font-weight: bold;
          margin: 20px 0 10px 0;
        }
        .mountain-signal-flow-diagram .parallel-flow {
          display: flex;
          justify-content: space-around;
          flex-wrap: wrap;
          margin: 20px 0;
        }
        .mountain-signal-flow-diagram .parallel-column {
          flex: 1;
          min-width: 300px;
          margin: 0 10px;
        }
        .mountain-signal-flow-diagram .info-box {
          background: rgba(255,255,255,0.2);
          border-left: 4px solid rgba(255,255,255,0.5);
          padding: 10px;
          margin: 10px 0;
          border-radius: 4px;
          color: white;
        }
        @media (max-width: 768px) {
          .mountain-signal-flow-diagram .parallel-flow {
            flex-direction: column;
          }
          .mountain-signal-flow-diagram .parallel-column {
            min-width: 100%;
            margin: 10px 0;
          }
        }
      `}</style>

      {/* Strategy Overview */}
      <div className="flow-container">
        <div className="flow-box start">
          <h5 className="mb-2">Capture Mountain Signal Strategy</h5>
          <div className="info-box" style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none' }}>
            <strong>Instruments:</strong> {strategy.instrument} ATM Options<br/>
            <strong>Timeframe:</strong> {candleTime} candles<br/>
            <strong>Indicator:</strong> {emaPeriod}-period EMA<br/>
            <strong>Execution:</strong> Every {candleTime} - 20 seconds<br/>
            <strong>Position Limit:</strong> One active signal & one trade at a time
          </div>
        </div>
      </div>

      {/* Main Flow Start */}
      <div className="flow-row">
        <div className="flow-column">
          <div className="flow-box process">
            <strong>Strategy Execution</strong><br/>
            Every {candleTime} - 20 seconds<br/>
            (e.g., 9:19:40, 9:24:40)
          </div>
          <div className="flow-arrow">↓</div>
          <div className="flow-box decision">
            Check Current Candle
          </div>
        </div>
      </div>

      {/* Parallel PE and CE Logic */}
      <div className="parallel-flow">
        {/* PE (Put Entry) Column */}
        <div className="parallel-column">
          <div className="section-title">PE (Put Entry) Logic</div>
          
          <div className="flow-column">
            <div className="flow-box signal">
              <strong>Signal Candle Identification</strong><br/>
              Candle's LOW &gt; {emaPeriod} EMA
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box decision" style={{ minWidth: '200px' }}>
              Mark as PE Signal Candle?
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box process">
              <strong>Entry Trigger Check</strong><br/>
              Next candle CLOSE &lt; Signal candle LOW?
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box entry">
              ✅ EXECUTE BUY PE TRADE
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box decision" style={{ minWidth: '200px' }}>
              Monitor Trade
            </div>
            <div className="flow-row">
              <div className="flow-column" style={{ flex: 1 }}>
                <div className="label-yes">Stop Loss</div>
                <div className="flow-box exit">
                  Price CLOSE &gt; Signal HIGH<br/>
                  ❌ EXIT PE
                </div>
              </div>
              <div className="flow-column" style={{ flex: 1 }}>
                <div className="label-yes">Target Check</div>
                <div className="flow-box decision">
                  HIGH &lt; {emaPeriod} EMA?<br/>
                  (At least 1 candle)
                </div>
                <div className="flow-arrow">↓</div>
                <div className="flow-box decision">
                  2 consecutive candles<br/>
                  CLOSE &gt; {emaPeriod} EMA?
                </div>
                <div className="flow-arrow">↓</div>
                <div className="flow-box exit">
                  ✅ EXIT PE (Target Hit)
                </div>
              </div>
            </div>
            <div className="flow-box process" style={{ marginTop: '20px', background: '#ff9800', color: 'white' }}>
              <strong>Signal Reset Condition</strong><br/>
              If next candle CLOSE &gt; signal HIGH<br/>
              AND Candle LOW &gt; {emaPeriod} EMA<br/>
              → New PE Signal Candle
            </div>
          </div>
        </div>

        {/* CE (Call Entry) Column */}
        <div className="parallel-column">
          <div className="section-title">CE (Call Entry) Logic</div>
          
          <div className="flow-column">
            <div className="flow-box signal">
              <strong>Signal Candle Identification</strong><br/>
              Candle's HIGH &lt; {emaPeriod} EMA
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box decision" style={{ minWidth: '200px' }}>
              Mark as CE Signal Candle?
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box process">
              <strong>Entry Trigger Check</strong><br/>
              Next candle CLOSE &gt; Signal candle HIGH?
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box entry">
              ✅ EXECUTE BUY CE TRADE
            </div>
            <div className="flow-arrow">↓</div>
            <div className="flow-box decision" style={{ minWidth: '200px' }}>
              Monitor Trade
            </div>
            <div className="flow-row">
              <div className="flow-column" style={{ flex: 1 }}>
                <div className="label-yes">Stop Loss</div>
                <div className="flow-box exit">
                  Price CLOSE &lt; Signal LOW<br/>
                  ❌ EXIT CE
                </div>
              </div>
              <div className="flow-column" style={{ flex: 1 }}>
                <div className="label-yes">Target Check</div>
                <div className="flow-box decision">
                  LOW &gt; {emaPeriod} EMA?<br/>
                  (At least 1 candle)
                </div>
                <div className="flow-arrow">↓</div>
                <div className="flow-box decision">
                  2 consecutive candles<br/>
                  CLOSE &lt; {emaPeriod} EMA?
                </div>
                <div className="flow-arrow">↓</div>
                <div className="flow-box exit">
                  ✅ EXIT CE (Target Hit)
                </div>
              </div>
            </div>
            <div className="flow-box process" style={{ marginTop: '20px', background: '#ff9800', color: 'white' }}>
              <strong>Signal Reset Condition</strong><br/>
              If next candle CLOSE &lt; signal LOW<br/>
              AND Candle HIGH &lt; {emaPeriod} EMA<br/>
              → New CE Signal Candle
            </div>
          </div>
        </div>
      </div>

      {/* Signal Memory and Rules */}
      <div className="flow-container" style={{ marginTop: '30px' }}>
        <div className="section-title">Signal Memory & Rules</div>
        <div className="flow-row">
          <div className="flow-box process" style={{ background: '#6c757d', color: 'white', flex: 1 }}>
            <strong>Signal Memory:</strong><br/>
            • Previous signal remains valid if no new signal found<br/>
            • Only one active signal type (CE or PE) at any time<br/>
            • Signal resets only when specific break conditions met
          </div>
          <div className="flow-box process" style={{ background: '#6c757d', color: 'white', flex: 1 }}>
            <strong>Trade Execution:</strong><br/>
            • One trade execution per signal candle<br/>
            • Re-entry on same signal candle allowed if no new signal found<br/>
            • Continuous monitoring every {candleTime} - 20 seconds
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flow-container" style={{ marginTop: '20px', background: '#f8f9fa', padding: '15px' }}>
        <h6 className="mb-3">Legend:</h6>
        <div className="d-flex flex-wrap gap-3">
          <div className="d-flex align-items-center">
            <div className="flow-box start" style={{ width: '30px', height: '30px', padding: '5px', margin: '0 10px 0 0' }}></div>
            <span>Start/Strategy Info</span>
          </div>
          <div className="d-flex align-items-center">
            <div className="flow-box signal" style={{ width: '30px', height: '30px', padding: '5px', margin: '0 10px 0 0' }}></div>
            <span>Signal Identification</span>
          </div>
          <div className="d-flex align-items-center">
            <div className="flow-box decision" style={{ width: '30px', height: '30px', padding: '5px', margin: '0 10px 0 0' }}></div>
            <span>Decision Point</span>
          </div>
          <div className="d-flex align-items-center">
            <div className="flow-box process" style={{ width: '30px', height: '30px', padding: '5px', margin: '0 10px 0 0' }}></div>
            <span>Process/Check</span>
          </div>
          <div className="d-flex align-items-center">
            <div className="flow-box entry" style={{ width: '30px', height: '30px', padding: '5px', margin: '0 10px 0 0' }}></div>
            <span>Entry Action</span>
          </div>
          <div className="d-flex align-items-center">
            <div className="flow-box exit" style={{ width: '30px', height: '30px', padding: '5px', margin: '0 10px 0 0' }}></div>
            <span>Exit Action</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MountainSignalFlowDiagram;

