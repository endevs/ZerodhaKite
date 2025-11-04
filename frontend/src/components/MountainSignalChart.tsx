import React, { useState, useEffect, useMemo } from 'react';
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Customized, XAxisProps, YAxisProps } from 'recharts';

interface Strategy {
  id: number;
  strategy_name: string;
  strategy_type: string;
  instrument: string;
  candle_time: string;
  ema_period?: number;
  start_time: string;
  end_time: string;
}

interface CandleData {
  x: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

interface ChartDataResponse {
  candles: CandleData[];
  ema5: Array<{ x: string; y: number | null }>;
  ema20?: Array<{ x: string; y: number | null }>;
  rsi14?: Array<{ x: string; y: number | null }>;
}

interface SignalCandle {
  index: number;
  type: 'PE' | 'CE';
  high: number;
  low: number;
  time: string;
}

interface TradeEvent {
  index: number;
  type: 'ENTRY' | 'EXIT' | 'STOP_LOSS' | 'TARGET' | 'MKT_CLOSE';
  tradeType: 'PE' | 'CE';
  price: number;
  time: string;
  signalCandleIndex: number;
}

interface IgnoredSignal {
  index: number;
  signalTime: string;
  signalType: 'PE' | 'CE';
  signalHigh: number;
  signalLow: number;
  reason: string;
  rsiValue: number | null;
}

interface MountainSignalChartProps {
  strategy: Strategy;
}

const MountainSignalChart: React.FC<MountainSignalChartProps> = ({ strategy }) => {
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [chartData, setChartData] = useState<ChartDataResponse>({ candles: [], ema5: [] });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [signalCandles, setSignalCandles] = useState<SignalCandle[]>([]);
  const [tradeEvents, setTradeEvents] = useState<TradeEvent[]>([]);
  const [peBreakLevel, setPeBreakLevel] = useState<number | null>(null);
  const [ceBreakLevel, setCeBreakLevel] = useState<number | null>(null);
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('line');
  const [ignoredSignals, setIgnoredSignals] = useState<IgnoredSignal[]>([]);
  const [tradeHistory, setTradeHistory] = useState<Array<{
    signalIndex: number;
    signalTime: string;
    signalType: 'PE' | 'CE';
    signalHigh: number;
    signalLow: number;
    entryIndex: number;
    entryTime: string;
    entryPrice: number;
    exitIndex: number | null;
    exitTime: string | null;
    exitPrice: number | null;
    exitType: 'STOP_LOSS' | 'TARGET' | 'MKT_CLOSE' | null;
    pnl: number | null;
    pnlPercent: number | null;
  }>>([]);

  const emaPeriod = strategy.ema_period || 5;
  const candleTime = parseInt(strategy.candle_time) || 5;

  // Set today's date as default
  useEffect(() => {
    const today = new Date().toISOString().split('T')[0];
    setSelectedDate(today);
  }, []);

  // Fetch chart data when date changes
  useEffect(() => {
    if (selectedDate) {
      fetchChartData();
    }
  }, [selectedDate, strategy]);

  const fetchChartData = async () => {
    if (!selectedDate) {
      setError('Please select a date');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8000/api/chart_data?date=${selectedDate}&instrument=${encodeURIComponent(strategy.instrument)}&interval=${candleTime}m`,
        { credentials: 'include' }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch chart data');
      }

      const data: ChartDataResponse = await response.json();
      setChartData(data);

      if (data.candles.length === 0) {
        setError('No data available for the selected date');
      } else {
        // Process Mountain Signal logic
        processMountainSignalLogic(data);
      }
    } catch (err) {
      console.error('Error fetching chart data:', err);
      setError(err instanceof Error ? err.message : 'An error occurred while fetching chart data');
    } finally {
      setLoading(false);
    }
  };

  const processMountainSignalLogic = (data: ChartDataResponse) => {
    const candles = data.candles;
    const ema5Values = data.ema5.map(e => e.y).filter(v => v !== null && v !== undefined) as number[];
    const rsi14Values = data.rsi14 ? data.rsi14.map(e => e.y).filter(v => v !== null && v !== undefined) as number[] : [];
    
    if (candles.length < emaPeriod + 1 || ema5Values.length < emaPeriod + 1) {
      return; // Not enough data
    }

    const signals: SignalCandle[] = [];
    const trades: TradeEvent[] = [];
    const ignored: IgnoredSignal[] = [];
    let currentPeSignal: SignalCandle | null = null;
    let currentCeSignal: SignalCandle | null = null;
    let activeTradeEvent: TradeEvent | null = null;
    let consecutiveCandlesForTarget: number = 0;
    let lastCandleHighLessThanEMA: boolean = false;
    let lastCandleLowGreaterThanEMA: boolean = false;
    // Track which signal candles have already had an entry
    const signalCandlesWithEntry = new Set<number>();
    // Track if price has traded above PE signal low / below CE signal high (required before entry)
    let peSignalPriceAboveLow: boolean = false;
    let ceSignalPriceBelowHigh: boolean = false;

    // Process each candle
    for (let i = emaPeriod; i < candles.length; i++) {
      const candle = candles[i];
      const prevCandle = candles[i - 1];
      const ema5 = ema5Values[i] || ema5Values[i - 1] || 0;
      const candleLow = candle.l;
      const candleHigh = candle.h;
      const candleClose = candle.c;
      const prevCandleClose = prevCandle.c;

      // Get RSI value for current candle (for signal identification only)
      const currentRsi = rsi14Values.length > i ? rsi14Values[i] : null;

      // PE Signal Candle Identification: LOW > 5 EMA AND RSI > 70
      if (candleLow > ema5) {
        // RSI condition must be met at signal identification time
        if (currentRsi !== null && currentRsi > 70) {
          // Signal Reset: If a newer candle meets the same criteria (LOW > 5 EMA + RSI > 70), 
          // it REPLACES the previous PE signal candle
          if (currentPeSignal) {
            // New PE signal candle identified - old signal candle is now invalid
            currentPeSignal = {
              index: i,
              type: 'PE',
              high: candleHigh,
              low: candleLow,
              time: candle.x
            };
            signals.push(currentPeSignal);
            // Old signal candle is replaced, reset price action tracking
            peSignalPriceAboveLow = false;
            // Clear entry tracking for old signal (new signal will start fresh)
            signalCandlesWithEntry.delete(currentPeSignal.index);
            setPeBreakLevel(null);
          } else {
            // First PE signal
            currentPeSignal = {
              index: i,
              type: 'PE',
              high: candleHigh,
              low: candleLow,
              time: candle.x
            };
            signals.push(currentPeSignal);
            // Reset price action tracking for new signal
            peSignalPriceAboveLow = false;
            // New signal candle starts fresh (no previous entries)
            signalCandlesWithEntry.delete(currentPeSignal.index);
          }
        }
        // If RSI condition not met, log as ignored (only if no current signal exists)
        else if (!currentPeSignal) {
          ignored.push({
            index: i,
            signalTime: candle.x,
            signalType: 'PE',
            signalHigh: candleHigh,
            signalLow: candleLow,
            reason: `Signal candle identified but RSI condition not met (RSI must be > 70, current: ${currentRsi !== null ? currentRsi.toFixed(2) : 'N/A'})`,
            rsiValue: currentRsi
          });
        }
      }

      // CE Signal Candle Identification: HIGH < 5 EMA AND RSI < 30
      if (candleHigh < ema5) {
        // RSI condition must be met at signal identification time
        if (currentRsi !== null && currentRsi < 30) {
          // Signal Reset: If a newer candle meets the same criteria (HIGH < 5 EMA + RSI < 30), 
          // it REPLACES the previous CE signal candle
          if (currentCeSignal) {
            // New CE signal candle identified - old signal candle is now invalid
            currentCeSignal = {
              index: i,
              type: 'CE',
              high: candleHigh,
              low: candleLow,
              time: candle.x
            };
            signals.push(currentCeSignal);
            // Old signal candle is replaced, reset price action tracking
            ceSignalPriceBelowHigh = false;
            // Clear entry tracking for old signal (new signal will start fresh)
            signalCandlesWithEntry.delete(currentCeSignal.index);
            setCeBreakLevel(null);
          } else {
            // First CE signal
            currentCeSignal = {
              index: i,
              type: 'CE',
              high: candleHigh,
              low: candleLow,
              time: candle.x
            };
            signals.push(currentCeSignal);
            // Reset price action tracking for new signal
            ceSignalPriceBelowHigh = false;
            // New signal candle starts fresh (no previous entries)
            signalCandlesWithEntry.delete(currentCeSignal.index);
          }
        }
        // If RSI condition not met, log as ignored (only if no current signal exists)
        else if (!currentCeSignal) {
          ignored.push({
            index: i,
            signalTime: candle.x,
            signalType: 'CE',
            signalHigh: candleHigh,
            signalLow: candleLow,
            reason: `Signal candle identified but RSI condition not met (RSI must be < 30, current: ${currentRsi !== null ? currentRsi.toFixed(2) : 'N/A'})`,
            rsiValue: currentRsi
          });
        }
      }

      // Track price action: Check if price has traded above PE signal low or below CE signal high
      // This validation is only needed AFTER a trade exit (stop loss or target), not before first entry
      if (currentPeSignal && !activeTradeEvent && !peSignalPriceAboveLow) {
        // Check if price (high) has traded above PE signal candle's low
        // Only check if no active trade (meaning we're waiting for re-entry after exit)
        if (candleHigh > currentPeSignal.low) {
          peSignalPriceAboveLow = true;
        }
      }
      
      if (currentCeSignal && !activeTradeEvent && !ceSignalPriceBelowHigh) {
        // Check if price (low) has traded below CE signal candle's high
        // Only check if no active trade (meaning we're waiting for re-entry after exit)
        if (candleLow < currentCeSignal.high) {
          ceSignalPriceBelowHigh = true;
        }
      }

      // Entry Triggers (only if no active trade)
      // RSI is checked only at signal identification, not at entry time
      if (!activeTradeEvent) {
        // PE Entry: Next candle CLOSE < signal candle LOW
        // For first entry: no price action validation needed
        // For re-entry after exit: price must have previously traded ABOVE the signal candle's low
        const isFirstEntry = !signalCandlesWithEntry.has(currentPeSignal?.index || -1);
        const peEntryAllowed = isFirstEntry || peSignalPriceAboveLow;
        
        if (currentPeSignal && candleClose < currentPeSignal.low && peEntryAllowed) {
          // Entry taken - signal candle already validated with RSI at identification time
          // and price action requirement met
          activeTradeEvent = {
            index: i,
            type: 'ENTRY',
            tradeType: 'PE',
            price: candleClose,
            time: candle.x,
            signalCandleIndex: currentPeSignal.index
          };
          trades.push(activeTradeEvent);
          signalCandlesWithEntry.add(currentPeSignal.index);
          setPeBreakLevel(currentPeSignal.low);
          // Reset price action validation after entry (for next exit/entry cycle)
          peSignalPriceAboveLow = false;
        }
        // CE Entry: Next candle CLOSE > signal candle HIGH
        // For first entry: no price action validation needed
        // For re-entry after exit: price must have previously traded BELOW the signal candle's high
        else {
          const isFirstEntry = !signalCandlesWithEntry.has(currentCeSignal?.index || -1);
          const ceEntryAllowed = isFirstEntry || ceSignalPriceBelowHigh;
          
          if (currentCeSignal && candleClose > currentCeSignal.high && ceEntryAllowed) {
          // Entry taken - signal candle already validated with RSI at identification time
          // and price action requirement met
          activeTradeEvent = {
            index: i,
            type: 'ENTRY',
            tradeType: 'CE',
            price: candleClose,
            time: candle.x,
            signalCandleIndex: currentCeSignal.index
          };
            trades.push(activeTradeEvent);
            signalCandlesWithEntry.add(currentCeSignal.index);
            setCeBreakLevel(currentCeSignal.high);
            // Reset price action validation after entry (for next exit/entry cycle)
            ceSignalPriceBelowHigh = false;
          }
        }
      }

      // Trade Management (if trade is active)
      if (activeTradeEvent) {
        const signalCandle = activeTradeEvent.tradeType === 'PE' ? currentPeSignal : currentCeSignal;
        if (!signalCandle) {
          activeTradeEvent = null;
          continue;
        }

        // Check for Market Close Square Off (15 minutes before market close at 3:30 PM)
        // Square off at 3:15 PM (15:15) or later
        const candleTime = new Date(candle.x);
        const candleHour = candleTime.getHours();
        const candleMinute = candleTime.getMinutes();
        const marketCloseSquareOffHour = 15; // 3 PM
        const marketCloseSquareOffMinute = 15; // 15 minutes
        
        // Check if current candle time is at or after 3:15 PM
        if (candleHour > marketCloseSquareOffHour || 
            (candleHour === marketCloseSquareOffHour && candleMinute >= marketCloseSquareOffMinute)) {
          // Square off the trade at market close
          const tradeType = activeTradeEvent.tradeType; // Save before nulling
          trades.push({
            index: i,
            type: 'MKT_CLOSE',
            tradeType: tradeType,
            price: candleClose,
            time: candle.x,
            signalCandleIndex: signalCandle.index
          });
          activeTradeEvent = null;
          // Keep signal active - don't reset it
          if (tradeType === 'PE') {
            setPeBreakLevel(null);
          } else {
            setCeBreakLevel(null);
          }
          consecutiveCandlesForTarget = 0;
          lastCandleHighLessThanEMA = false;
          lastCandleLowGreaterThanEMA = false;
          continue; // Move to next candle
        }

        // Stop Loss for PE: Price closes above signal candle HIGH
        if (activeTradeEvent.tradeType === 'PE' && candleClose > signalCandle.high) {
          trades.push({
            index: i,
            type: 'STOP_LOSS',
            tradeType: 'PE',
            price: candleClose,
            time: candle.x,
            signalCandleIndex: signalCandle.index
          });
          activeTradeEvent = null;
          // Keep currentPeSignal active - don't reset it, signal candle remains valid for next entry
          // Reset price action validation after exit (for next entry)
          peSignalPriceAboveLow = false;
          setPeBreakLevel(null);
          consecutiveCandlesForTarget = 0;
          lastCandleHighLessThanEMA = false;
        }
        // Stop Loss for CE: Price closes below signal candle LOW
        else if (activeTradeEvent.tradeType === 'CE' && candleClose < signalCandle.low) {
          trades.push({
            index: i,
            type: 'STOP_LOSS',
            tradeType: 'CE',
            price: candleClose,
            time: candle.x,
            signalCandleIndex: signalCandle.index
          });
          activeTradeEvent = null;
          // Keep currentCeSignal active - don't reset it, signal candle remains valid for next entry
          // Reset price action validation after exit (for next entry)
          ceSignalPriceBelowHigh = false;
          setCeBreakLevel(null);
          consecutiveCandlesForTarget = 0;
          lastCandleLowGreaterThanEMA = false;
        }
        // Target for PE: Wait for HIGH < EMA, then 2 consecutive CLOSE > EMA
        else if (activeTradeEvent.tradeType === 'PE') {
          if (candleHigh < ema5) {
            lastCandleHighLessThanEMA = true;
          }
          if (lastCandleHighLessThanEMA && candleClose > ema5) {
            consecutiveCandlesForTarget++;
            if (consecutiveCandlesForTarget >= 2) {
              trades.push({
                index: i,
                type: 'TARGET',
                tradeType: 'PE',
                price: candleClose,
                time: candle.x,
                signalCandleIndex: signalCandle.index
              });
              activeTradeEvent = null;
              // Keep currentPeSignal active - don't reset it, signal candle remains valid for next entry
              // Reset price action validation after exit (for next entry)
              peSignalPriceAboveLow = false;
              setPeBreakLevel(null);
              consecutiveCandlesForTarget = 0;
              lastCandleHighLessThanEMA = false;
            }
          } else if (candleClose <= ema5) {
            consecutiveCandlesForTarget = 0;
          }
        }
        // Target for CE: Wait for LOW > EMA, then 2 consecutive CLOSE < EMA
        else if (activeTradeEvent.tradeType === 'CE') {
          if (candleLow > ema5) {
            lastCandleLowGreaterThanEMA = true;
          }
          if (lastCandleLowGreaterThanEMA && candleClose < ema5) {
            consecutiveCandlesForTarget++;
            if (consecutiveCandlesForTarget >= 2) {
              trades.push({
                index: i,
                type: 'TARGET',
                tradeType: 'CE',
                price: candleClose,
                time: candle.x,
                signalCandleIndex: signalCandle.index
              });
              activeTradeEvent = null;
              // Keep currentCeSignal active - don't reset it, signal candle remains valid for next entry
              // Reset price action validation after exit (for next entry)
              ceSignalPriceBelowHigh = false;
              setCeBreakLevel(null);
              consecutiveCandlesForTarget = 0;
              lastCandleLowGreaterThanEMA = false;
            }
          } else if (candleClose >= ema5) {
            consecutiveCandlesForTarget = 0;
          }
        }
      }
    }

    setSignalCandles(signals);
    setTradeEvents(trades);
    setIgnoredSignals(ignored);

    // Build trade history for table
    const history: typeof tradeHistory = [];
    let activeTradeHistory: {
      signalIndex: number;
      signalTime: string;
      signalType: 'PE' | 'CE';
      signalHigh: number;
      signalLow: number;
      entryIndex: number;
      entryTime: string;
      entryPrice: number;
      exitIndex: number | null;
      exitTime: string | null;
      exitPrice: number | null;
      exitType: 'STOP_LOSS' | 'TARGET' | 'MKT_CLOSE' | null;
      pnl: number | null;
      pnlPercent: number | null;
    } | null = null;

    for (const event of trades) {
      if (event.type === 'ENTRY') {
        const signalCandle = signals.find(s => s.index === event.signalCandleIndex);
        if (signalCandle) {
          activeTradeHistory = {
            signalIndex: signalCandle.index,
            signalTime: signalCandle.time,
            signalType: signalCandle.type,
            signalHigh: signalCandle.high,
            signalLow: signalCandle.low,
            entryIndex: event.index,
            entryTime: event.time,
            entryPrice: event.price,
            exitIndex: null,
            exitTime: null,
            exitPrice: null,
            exitType: null,
            pnl: null,
            pnlPercent: null
          };
        }
      } else if (activeTradeHistory && (event.type === 'STOP_LOSS' || event.type === 'TARGET' || event.type === 'MKT_CLOSE')) {
        activeTradeHistory.exitIndex = event.index;
        activeTradeHistory.exitTime = event.time;
        activeTradeHistory.exitPrice = event.price;
        activeTradeHistory.exitType = event.type;
        
        // Calculate P&L
        if (activeTradeHistory.signalType === 'PE') {
          // PE: Profit when price goes down (exit < entry)
          activeTradeHistory.pnl = (activeTradeHistory.entryPrice - activeTradeHistory.exitPrice) * 50; // Assuming 50 units per lot
          activeTradeHistory.pnlPercent = ((activeTradeHistory.entryPrice - activeTradeHistory.exitPrice) / activeTradeHistory.entryPrice) * 100;
        } else {
          // CE: Profit when price goes up (exit > entry)
          activeTradeHistory.pnl = (activeTradeHistory.exitPrice - activeTradeHistory.entryPrice) * 50;
          activeTradeHistory.pnlPercent = ((activeTradeHistory.exitPrice - activeTradeHistory.entryPrice) / activeTradeHistory.entryPrice) * 100;
        }
        
        history.push({ ...activeTradeHistory });
        activeTradeHistory = null;
      }
    }

    // If there's an open trade, add it without exit
    if (activeTradeHistory) {
      history.push(activeTradeHistory);
    }

    setTradeHistory(history);
  };

  // Format time for display
  const formatTime = (dateString: string): string => {
    const date = new Date(dateString);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  // Prepare chart data with indicators and markers
  const chartDataFormatted = useMemo(() => {
    return chartData.candles.map((candle, index) => {
      const ema5Value = chartData.ema5?.[index]?.y ?? null;
      const rsi14Value = chartData.rsi14?.[index]?.y ?? null;
      const signalCandle = signalCandles.find(s => s.index === index);
      const tradeEvent = tradeEvents.find(t => t.index === index);

      return {
        time: new Date(candle.x),
        timeFormatted: formatTime(candle.x),
        open: candle.o,
        high: candle.h,
        low: candle.l,
        close: candle.c,
        ema5: ema5Value,
        rsi14: rsi14Value,
        isSignalCandle: !!signalCandle,
        signalType: signalCandle?.type || null,
        tradeEvent: tradeEvent || null,
        // For candlestick rendering
        ohlc: [candle.o, candle.h, candle.l, candle.c]
      };
    });
  }, [chartData, signalCandles, tradeEvents]);

  // Enhanced Custom Tooltip with full details
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const candleIndex = chartDataFormatted.findIndex(c => c.timeFormatted === label);
      const signalCandle = signalCandles.find(s => s.index === candleIndex);
      const tradeEvent = tradeEvents.find(t => t.index === candleIndex);
      const trade = tradeHistory.find(t => 
        t.signalIndex === candleIndex || 
        t.entryIndex === candleIndex || 
        t.exitIndex === candleIndex
      );

      return (
        <div className="bg-white border shadow-lg p-3 rounded" style={{ minWidth: '250px', maxWidth: '350px' }}>
          <p className="fw-bold mb-2 border-bottom pb-2">{formatDateTime(data.time.toISOString())}</p>
          
          {/* OHLC Data */}
          <div className="mb-2">
            <p className="mb-1 small"><strong>Open:</strong> <span className="text-primary">{data.open.toFixed(2)}</span></p>
            <p className="mb-1 small"><strong>High:</strong> <span className="text-success">{data.high.toFixed(2)}</span></p>
            <p className="mb-1 small"><strong>Low:</strong> <span className="text-danger">{data.low.toFixed(2)}</span></p>
            <p className="mb-1 small"><strong>Close:</strong> <span className="text-info">{data.close.toFixed(2)}</span></p>
          </div>

          {/* EMA */}
          {data.ema5 && (
            <p className="mb-2 small border-top pt-2" style={{ color: '#ff6b35' }}>
              <strong>EMA {emaPeriod}:</strong> {data.ema5.toFixed(2)}
            </p>
          )}

          {/* RSI */}
          {data.rsi14 !== null && data.rsi14 !== undefined && (
            <p className="mb-2 small border-top pt-2" style={{ color: '#82ca9d' }}>
              <strong>RSI 14:</strong> {data.rsi14.toFixed(2)}
              {data.rsi14 > 70 && <span className="ms-2 text-danger">(Overbought)</span>}
              {data.rsi14 < 30 && <span className="ms-2 text-success">(Oversold)</span>}
            </p>
          )}

          {/* Signal Candle Info */}
          {signalCandle && (
            <div className="mb-2 border-top pt-2" style={{ backgroundColor: signalCandle.type === 'PE' ? '#fff5f5' : '#f0fff4', padding: '8px', borderRadius: '4px' }}>
              <p className="mb-1 small fw-bold" style={{ color: signalCandle.type === 'PE' ? '#dc3545' : '#28a745' }}>
                🎯 Signal Candle ({signalCandle.type})
              </p>
              <p className="mb-0 small"><strong>High:</strong> {signalCandle.high.toFixed(2)}</p>
              <p className="mb-0 small"><strong>Low:</strong> {signalCandle.low.toFixed(2)}</p>
            </div>
          )}

          {/* Trade Event Info */}
          {tradeEvent && (
            <div className="mb-2 border-top pt-2" style={{ backgroundColor: tradeEvent.type === 'ENTRY' ? '#f0fff4' : tradeEvent.type === 'STOP_LOSS' ? '#fff5f5' : '#fffbf0', padding: '8px', borderRadius: '4px' }}>
              <p className="mb-1 small fw-bold" style={{ color: tradeEvent.type === 'ENTRY' ? '#28a745' : tradeEvent.type === 'STOP_LOSS' ? '#dc3545' : '#ffc107' }}>
                {tradeEvent.type === 'ENTRY' ? '✅' : tradeEvent.type === 'STOP_LOSS' ? '❌' : '🎯'} {tradeEvent.type} ({tradeEvent.tradeType})
              </p>
              <p className="mb-0 small"><strong>Price:</strong> {tradeEvent.price.toFixed(2)}</p>
            </div>
          )}

          {/* Trade History Info */}
          {trade && (
            <div className="mb-0 border-top pt-2" style={{ backgroundColor: '#f8f9fa', padding: '8px', borderRadius: '4px' }}>
              <p className="mb-1 small fw-bold">Trade Details:</p>
              <p className="mb-0 small"><strong>Signal:</strong> {formatDateTime(trade.signalTime)}</p>
              <p className="mb-0 small"><strong>Entry:</strong> {formatDateTime(trade.entryTime)} @ {trade.entryPrice.toFixed(2)}</p>
              {trade.exitTime && (
                <>
                  <p className="mb-0 small">
                    <strong>Exit:</strong> {formatDateTime(trade.exitTime)} @ {trade.exitPrice?.toFixed(2)} 
                    <span className="ms-1">({trade.exitType === 'MKT_CLOSE' ? 'Market Close' : trade.exitType})</span>
                  </p>
                  {trade.pnl !== null && trade.pnlPercent !== null && (
                    <p className="mb-0 small fw-bold" style={{ color: trade.pnl >= 0 ? '#28a745' : '#dc3545' }}>
                      P&L: {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)} ({trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(2)}%)
                    </p>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  const formatDateTime = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  };

  // Custom Candlestick Component for Recharts
  const CandlestickRenderer = (props: any) => {
    try {
      const { xAxisMap, yAxisMap } = props;
      if (!xAxisMap || !yAxisMap) return null;
      
      const xKey = Object.keys(xAxisMap)[0];
      const yKey = Object.keys(yAxisMap)[0];
      
      if (!xKey || !yKey) return null;

      const xAxis = xAxisMap[xKey];
      const yAxis = yAxisMap[yKey];
      const xScale = xAxis?.scale;
      const yScale = yAxis?.scale;
      
      if (!xScale || !yScale) return null;

      // Calculate band size for categorical axis
      const dataLength = chartDataFormatted.length;
      const chartWidth = props.width || 800;
      const bandSize = dataLength > 0 ? chartWidth / dataLength : 10;
      const candleWidth = Math.max(4, Math.floor(bandSize * 0.5));
      const half = Math.floor(candleWidth / 2);

      return (
        <g>
          {chartDataFormatted.map((candle, index) => {
            let xPos: number;
            if (typeof xScale === 'function') {
              xPos = xScale(candle.timeFormatted);
            } else if (xScale && typeof xScale.bandwidth === 'function') {
              xPos = xScale(candle.timeFormatted) || (index * bandSize);
            } else {
              xPos = index * bandSize;
            }

            if (typeof xPos !== 'number' || isNaN(xPos)) return null;

            const centerX = xPos + (bandSize / 2);
            const startX = centerX - half;

            const isRising = candle.close >= candle.open;
            const highY = yScale(candle.high);
            const lowY = yScale(candle.low);
            const openY = yScale(candle.open);
            const closeY = yScale(candle.close);

            if ([highY, lowY, openY, closeY].some(v => typeof v !== 'number' || isNaN(v))) return null;

            const bodyTop = isRising ? closeY : openY;
            const bodyBottom = isRising ? openY : closeY;
            const bodyHeight = Math.max(2, Math.abs(bodyBottom - bodyTop));

            const signalCandle = signalCandles.find(s => s.index === index);
            const tradeEvent = tradeEvents.find(t => t.index === index);
            const borderColor = signalCandle 
              ? (signalCandle.type === 'PE' ? '#dc3545' : '#28a745')
              : 'transparent';
            const borderWidth = signalCandle ? 3 : 0;

            return (
              <g key={index}>
                {/* Wick */}
                <line
                  x1={centerX}
                  y1={highY}
                  x2={centerX}
                  y2={lowY}
                  stroke={isRising ? '#28a745' : '#dc3545'}
                  strokeWidth={2}
                />
                {/* Body */}
                <rect
                  x={startX}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                  fill={isRising ? '#28a745' : '#dc3545'}
                  stroke={borderColor}
                  strokeWidth={borderWidth}
                  opacity={0.9}
                />
                {/* Entry marker */}
                {tradeEvent?.type === 'ENTRY' && (
                  <g>
                    <circle
                      cx={centerX}
                      cy={yScale(tradeEvent.price)}
                      r={8}
                      fill={tradeEvent.tradeType === 'PE' ? '#dc3545' : '#28a745'}
                      stroke="white"
                      strokeWidth={2}
                    />
                    <text
                      x={centerX}
                      y={yScale(tradeEvent.price) - 12}
                      textAnchor="middle"
                      fill={tradeEvent.tradeType === 'PE' ? '#dc3545' : '#28a745'}
                      fontSize="10"
                      fontWeight="bold"
                    >
                      ENTRY
                    </text>
                  </g>
                )}
                {/* Exit marker */}
                {(tradeEvent?.type === 'STOP_LOSS' || tradeEvent?.type === 'TARGET' || tradeEvent?.type === 'MKT_CLOSE') && (
                  <g>
                    <circle
                      cx={centerX}
                      cy={yScale(tradeEvent.price)}
                      r={8}
                      fill={tradeEvent.type === 'STOP_LOSS' ? '#dc3545' : tradeEvent.type === 'MKT_CLOSE' ? '#6c757d' : '#ffc107'}
                      stroke="white"
                      strokeWidth={2}
                    />
                    <text
                      x={centerX}
                      y={yScale(tradeEvent.price) - 12}
                      textAnchor="middle"
                      fill={tradeEvent.type === 'STOP_LOSS' ? '#dc3545' : tradeEvent.type === 'MKT_CLOSE' ? '#6c757d' : '#ffc107'}
                      fontSize="10"
                      fontWeight="bold"
                    >
                      {tradeEvent.type === 'STOP_LOSS' ? 'SL' : tradeEvent.type === 'MKT_CLOSE' ? 'MC' : 'TP'}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      );
    } catch (e) {
      console.error('Error rendering candlesticks:', e);
      return null;
    }
  };

  return (
    <div className="mountain-signal-chart">
      <div className="card border-0 shadow-sm mb-3">
        <div className="card-body">
          <div className="row align-items-end mb-3">
            <div className="col-md-4">
              <label htmlFor="chart-date-picker" className="form-label fw-bold">
                <i className="bi bi-calendar3 me-2"></i>Select Date
              </label>
              <input
                type="date"
                id="chart-date-picker"
                className="form-control"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                max={new Date().toISOString().split('T')[0]}
              />
            </div>
            <div className="col-md-3">
              <label htmlFor="chart-type-select" className="form-label fw-bold">
                <i className="bi bi-bar-chart me-2"></i>Chart Type
              </label>
              <select
                id="chart-type-select"
                className="form-select"
                value={chartType}
                onChange={(e) => setChartType(e.target.value as 'candlestick' | 'line')}
              >
                <option value="candlestick">Candlestick</option>
                <option value="line">Line</option>
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label">&nbsp;</label>
              <button
                className="btn btn-primary w-100"
                onClick={fetchChartData}
                disabled={loading || !selectedDate}
              >
                {loading ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                    Loading...
                  </>
                ) : (
                  <>
                    <i className="bi bi-graph-up-arrow me-2"></i>Load Chart
                  </>
                )}
              </button>
            </div>
            <div className="col-md-3">
              <div className="text-muted small">
                <strong>Strategy:</strong> {strategy.strategy_name}<br/>
                <strong>Instrument:</strong> {strategy.instrument} | <strong>EMA:</strong> {emaPeriod}
              </div>
            </div>
          </div>

          {error && (
            <div className="alert alert-warning" role="alert">
              <i className="bi bi-exclamation-triangle me-2"></i>{error}
            </div>
          )}

          {chartDataFormatted.length > 0 && (
            <div className="mb-3">
              <div className="row text-center">
                <div className="col-md-3">
                  <span className="badge bg-danger me-2">PE Signal</span>
                  <span className="badge bg-success me-2">CE Signal</span>
                </div>
                <div className="col-md-3">
                  <span className="badge bg-success me-2">Entry</span>
                  <span className="badge bg-danger me-2">Stop Loss</span>
                  <span className="badge bg-warning me-2">Target</span>
                </div>
                <div className="col-md-3">
                  <small className="text-muted">
                    Signals Found: <strong>{signalCandles.length}</strong>
                  </small>
                </div>
                <div className="col-md-3">
                  <small className="text-muted">
                    Trades: <strong>{tradeEvents.filter(t => t.type === 'ENTRY').length}</strong>
                  </small>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {chartDataFormatted.length > 0 && (
        <div className="card border-0 shadow-sm">
          <div className="card-body">
            <h5 className="card-title mb-3">
              <i className="bi bi-bar-chart-fill me-2"></i>
              Mountain Signal Strategy Chart
            </h5>
            <div style={{ width: '100%', height: '600px', minWidth: 0 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={chartDataFormatted}
                  margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                  <XAxis
                    dataKey="timeFormatted"
                    type="category"
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    stroke="#666"
                    style={{ fontSize: '12px' }}
                    interval={Math.floor(chartDataFormatted.length / 20)} // Show ~20 labels
                  />
                  <YAxis
                    stroke="#666"
                    style={{ fontSize: '12px' }}
                    domain={['dataMin - 10', 'dataMax + 10']}
                  />
                  {/* RSI YAxis (0-100 scale) */}
                  {chartDataFormatted.some(c => c.rsi14 !== null && c.rsi14 !== undefined) && (
                    <YAxis
                      yAxisId="rsi"
                      orientation="right"
                      stroke="#82ca9d"
                      style={{ fontSize: '12px' }}
                      domain={[0, 100]}
                      label={{ value: 'RSI', angle: -90, position: 'insideRight' }}
                    />
                  )}
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  
                  {/* EMA Line */}
                  {chartDataFormatted.some(c => c.ema5 !== null) && (
                    <Line
                      type="monotone"
                      dataKey="ema5"
                      stroke="#ff6b35"
                      strokeWidth={2}
                      dot={false}
                      name={`EMA ${emaPeriod}`}
                      connectNulls={false}
                    />
                  )}

                  {/* RSI 14 Line (on separate Y-axis) */}
                  {chartDataFormatted.some(c => c.rsi14 !== null && c.rsi14 !== undefined) && (
                    <Line
                      type="monotone"
                      dataKey="rsi14"
                      stroke="#82ca9d"
                      strokeWidth={2}
                      dot={false}
                      name="RSI 14"
                      connectNulls={false}
                      yAxisId="rsi"
                    />
                  )}

                  {/* RSI 14 Reference Lines (Thresholds) */}
                  {chartDataFormatted.some(c => c.rsi14 !== null && c.rsi14 !== undefined) && (
                    <>
                      <ReferenceLine yAxisId="rsi" y={70} stroke="#dc3545" strokeDasharray="3 3" strokeWidth={1} label={{ value: 'RSI 70 (PE Entry)', position: 'right', fill: '#dc3545' }} />
                      <ReferenceLine yAxisId="rsi" y={30} stroke="#28a745" strokeDasharray="3 3" strokeWidth={1} label={{ value: 'RSI 30 (CE Entry)', position: 'right', fill: '#28a745' }} />
                    </>
                  )}

                  {/* PE Break Level Reference Line */}
                  {peBreakLevel && (
                    <ReferenceLine
                      y={peBreakLevel}
                      stroke="#dc3545"
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      label={{ value: 'PE Break Level', position: 'right', fill: '#dc3545' }}
                    />
                  )}

                  {/* CE Break Level Reference Line */}
                  {ceBreakLevel && (
                    <ReferenceLine
                      y={ceBreakLevel}
                      stroke="#28a745"
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      label={{ value: 'CE Break Level', position: 'right', fill: '#28a745' }}
                    />
                  )}

                  {/* Chart based on type */}
                  {chartType === 'candlestick' ? (
                    <>
                      {/* Custom Candlestick Renderer */}
                      <Customized component={CandlestickRenderer} />
                      {/* Invisible line to trigger tooltip */}
                      <Line
                        type="monotone"
                        dataKey="close"
                        stroke="transparent"
                        strokeWidth={0}
                        dot={false}
                        activeDot={false}
                        connectNulls={false}
                      />
                    </>
                  ) : (
                    <>
                      {/* Line Chart */}
                      <Line
                        type="monotone"
                        dataKey="close"
                        stroke="#8884d8"
                        strokeWidth={2}
                        dot={false}
                        name="Close Price"
                        connectNulls={false}
                      />
                      {/* Entry markers on line */}
                      {tradeEvents.filter(e => e.type === 'ENTRY').map((event, idx) => {
                        const candle = chartDataFormatted[event.index];
                        if (!candle) return null;
                        return (
                          <ReferenceLine
                            key={`entry-${idx}`}
                            x={candle.timeFormatted}
                            stroke={event.tradeType === 'PE' ? '#dc3545' : '#28a745'}
                            strokeDasharray="3 3"
                            strokeWidth={2}
                            label={{ value: `ENTRY ${event.tradeType}`, position: 'top', fill: event.tradeType === 'PE' ? '#dc3545' : '#28a745' }}
                          />
                        );
                      })}
                      {/* Exit markers on line */}
                      {tradeEvents.filter(e => e.type === 'STOP_LOSS' || e.type === 'TARGET').map((event, idx) => {
                        const candle = chartDataFormatted[event.index];
                        if (!candle) return null;
                        return (
                          <ReferenceLine
                            key={`exit-${idx}`}
                            x={candle.timeFormatted}
                            stroke={event.type === 'STOP_LOSS' ? '#dc3545' : '#ffc107'}
                            strokeDasharray="3 3"
                            strokeWidth={2}
                            label={{ value: event.type, position: 'bottom', fill: event.type === 'STOP_LOSS' ? '#dc3545' : '#ffc107' }}
                          />
                        );
                      })}
                    </>
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {!loading && chartDataFormatted.length === 0 && !error && (
        <div className="card border-0 shadow-sm">
          <div className="card-body text-center py-5">
            <i className="bi bi-graph-up" style={{ fontSize: '4rem', opacity: 0.3, color: '#6c757d' }}></i>
            <p className="mt-3 text-muted">Select a date and click "Load Chart" to view the Mountain Signal strategy visualization</p>
          </div>
        </div>
      )}

      {/* Ignored Signals Table */}
      {ignoredSignals.length > 0 && (
        <div className="card border-0 shadow-sm mt-3">
          <div className="card-header bg-warning text-dark">
            <h5 className="card-title mb-0">
              <i className="bi bi-exclamation-triangle me-2"></i>
              Ignored Signals (RSI Condition Not Met)
            </h5>
          </div>
          <div className="card-body">
            <div className="table-responsive">
              <table className="table table-hover table-striped">
                <thead className="table-warning">
                  <tr>
                    <th>#</th>
                    <th>Signal Time</th>
                    <th>Signal Type</th>
                    <th>Signal High</th>
                    <th>Signal Low</th>
                    <th>RSI Value</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {ignoredSignals.map((signal, index) => (
                    <tr key={index}>
                      <td><strong>{index + 1}</strong></td>
                      <td>{formatDateTime(signal.signalTime)}</td>
                      <td>
                        <span className={`badge ${signal.signalType === 'PE' ? 'bg-danger' : 'bg-success'}`}>
                          {signal.signalType}
                        </span>
                      </td>
                      <td>{signal.signalHigh.toFixed(2)}</td>
                      <td>{signal.signalLow.toFixed(2)}</td>
                      <td>
                        {signal.rsiValue !== null ? (
                          <span className={signal.signalType === 'PE' && signal.rsiValue <= 70 ? 'text-danger' : signal.signalType === 'CE' && signal.rsiValue >= 30 ? 'text-danger' : 'text-muted'}>
                            {signal.rsiValue.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-muted">N/A</span>
                        )}
                      </td>
                      <td>
                        <small className="text-muted">{signal.reason}</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Trade History Table */}
      {tradeHistory.length > 0 && (
        <div className="card border-0 shadow-sm mt-3">
          <div className="card-header bg-info text-white">
            <h5 className="card-title mb-0">
              <i className="bi bi-table me-2"></i>
              Trade History & P&L Analysis
            </h5>
          </div>
          <div className="card-body">
            <div className="table-responsive">
              <table className="table table-hover table-striped">
                <thead className="table-dark">
                  <tr>
                    <th>#</th>
                    <th>Signal Time</th>
                    <th>Signal Type</th>
                    <th>Signal High</th>
                    <th>Signal Low</th>
                    <th>Entry Time</th>
                    <th>Entry Price</th>
                    <th>Exit Time</th>
                    <th>Exit Price</th>
                    <th>Exit Type</th>
                    <th>P&L</th>
                    <th>P&L %</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeHistory.map((trade, index) => (
                    <tr key={index}>
                      <td><strong>{index + 1}</strong></td>
                      <td>{formatDateTime(trade.signalTime)}</td>
                      <td>
                        <span className={`badge ${trade.signalType === 'PE' ? 'bg-danger' : 'bg-success'}`}>
                          {trade.signalType}
                        </span>
                      </td>
                      <td>{trade.signalHigh.toFixed(2)}</td>
                      <td>{trade.signalLow.toFixed(2)}</td>
                      <td>{formatDateTime(trade.entryTime)}</td>
                      <td><strong>{trade.entryPrice.toFixed(2)}</strong></td>
                      <td>{trade.exitTime ? formatDateTime(trade.exitTime) : <span className="text-muted">-</span>}</td>
                      <td>{trade.exitPrice ? trade.exitPrice.toFixed(2) : <span className="text-muted">-</span>}</td>
                      <td>
                        {trade.exitType ? (
                          <span className={`badge ${
                            trade.exitType === 'STOP_LOSS' ? 'bg-danger' : 
                            trade.exitType === 'MKT_CLOSE' ? 'bg-secondary' : 
                            'bg-warning'
                          }`}>
                            {trade.exitType === 'STOP_LOSS' ? 'Stop Loss' : 
                             trade.exitType === 'MKT_CLOSE' ? 'Market Close' : 
                             'Target'}
                          </span>
                        ) : (
                          <span className="text-muted">-</span>
                        )}
                      </td>
                      <td>
                        {trade.pnl !== null ? (
                          <span className={`fw-bold ${trade.pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                            {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-muted">-</span>
                        )}
                      </td>
                      <td>
                        {trade.pnlPercent !== null ? (
                          <span className={`fw-bold ${trade.pnlPercent >= 0 ? 'text-success' : 'text-danger'}`}>
                            {trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(2)}%
                          </span>
                        ) : (
                          <span className="text-muted">-</span>
                        )}
                      </td>
                      <td>
                        {trade.exitTime ? (
                          <span className="badge bg-secondary">Closed</span>
                        ) : (
                          <span className="badge bg-success">Open</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {/* Summary Row */}
                  <tr className="table-info fw-bold">
                    <td colSpan={10} className="text-end">Total P&L:</td>
                    <td>
                      {(() => {
                        const totalPnL = tradeHistory
                          .filter(t => t.pnl !== null)
                          .reduce((sum, t) => sum + (t.pnl || 0), 0);
                        return (
                          <span className={totalPnL >= 0 ? 'text-success' : 'text-danger'}>
                            {totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(2)}
                          </span>
                        );
                      })()}
                    </td>
                    <td>
                      {(() => {
                        const totalPnLPercent = tradeHistory
                          .filter(t => t.pnlPercent !== null)
                          .reduce((sum, t) => sum + (t.pnlPercent || 0), 0);
                        return (
                          <span className={totalPnLPercent >= 0 ? 'text-success' : 'text-danger'}>
                            {totalPnLPercent >= 0 ? '+' : ''}{totalPnLPercent.toFixed(2)}%
                          </span>
                        );
                      })()}
                    </td>
                    <td>
                      <span className="badge bg-primary">
                        {tradeHistory.filter(t => t.exitTime).length} / {tradeHistory.length} Closed
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MountainSignalChart;

