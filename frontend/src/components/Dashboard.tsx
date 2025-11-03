import React, { useState, useEffect, useCallback } from 'react';
import Layout from './Layout';
import Navigation from './Navigation';
import { io, Socket } from 'socket.io-client';
import DashboardContent from './DashboardContent';
import BacktestContent from './BacktestContent';
import MarketReplayContent from './MarketReplayContent';
import TickDataContent from './TickDataContent';
import ChartContent from './ChartContent';
import ChartModal from './ChartModal';
import EnhancedRealTimeStrategyMonitor from './EnhancedRealTimeStrategyMonitor';

const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [userName, setUserName] = useState<string>('Guest');
  const [niftyPrice, setNiftyPrice] = useState<string>('Loading...');
  const [bankNiftyPrice, setBankNiftyPrice] = useState<string>('Loading...');
  const [balance, setBalance] = useState<string>('0.00');
  const [accessToken, setAccessToken] = useState<boolean>(false);

  const [showChartModal, setShowChartModal] = useState<boolean>(false);
  const [chartInstrumentToken, setChartInstrumentToken] = useState<string | undefined>(undefined);
  const [showLiveStrategyModal, setShowLiveStrategyModal] = useState<boolean>(false);
  const [liveStrategyId, setLiveStrategyId] = useState<string | null>(null);

  const handleViewChart = useCallback((instrumentToken: string) => {
    setChartInstrumentToken(instrumentToken);
    setShowChartModal(true);
  }, []);

  const handleCloseChartModal = useCallback(() => {
    setShowChartModal(false);
    setChartInstrumentToken(undefined);
  }, []);

  const handleViewLiveStrategy = useCallback((strategyId: string) => {
    setLiveStrategyId(strategyId);
    setShowLiveStrategyModal(true);
  }, []);

  const handleCloseLiveStrategyModal = useCallback(() => {
    setShowLiveStrategyModal(false);
    setLiveStrategyId(null);
  }, []);

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/user-data', { credentials: 'include' });
        const data = await response.json();
        if (response.ok) {
          setUserName(data.user_name || 'User');
          setBalance(data.balance ? data.balance.toFixed(2) : '0.00');
          setAccessToken(data.access_token_present || false);
        } else {
          console.error('Error fetching user data:', data.message);
        }
      } catch (error) {
        console.error('Error fetching user data:', error);
      }
    };

    const fetchInitialMarketData = async () => {
      // Try to get initial market data if available
      try {
        // This could be an API endpoint if you add one, or use WebSocket only
        // For now, rely on WebSocket
      } catch (error) {
        console.error('Error fetching initial market data:', error);
      }
    };

    fetchUserData();
    fetchInitialMarketData();

    const socket: Socket = io('http://localhost:8000', {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    socket.on('connect', () => {
      console.log('Connected to WebSocket');
      socket.emit('my_event', { data: 'I\'m connected!' });
    });

    socket.on('connect_error', (error: any) => {
      console.error('WebSocket connection error:', error);
      setNiftyPrice('Connection Error');
      setBankNiftyPrice('Connection Error');
    });

    socket.on('unauthorized', (msg: { message: string }) => {
      alert(msg.message);
      window.location.href = '/login'; // Redirect to login page
    });

    socket.on('market_data', (msg: any) => {
      // Handle both separate and combined market data formats
      if (msg.nifty_price) {
        // Convert to number and format if needed
        const price = typeof msg.nifty_price === 'string' ? msg.nifty_price : msg.nifty_price.toFixed(2);
        setNiftyPrice(price);
      }
      if (msg.banknifty_price) {
        const price = typeof msg.banknifty_price === 'string' ? msg.banknifty_price : msg.banknifty_price.toFixed(2);
        setBankNiftyPrice(price);
      }
      // Also handle the new format with instrument_token
      if (msg.instrument_token === 256265 && msg.last_price !== undefined) {
        setNiftyPrice(typeof msg.last_price === 'number' ? msg.last_price.toFixed(2) : String(msg.last_price));
      }
      if (msg.instrument_token === 260105 && msg.last_price !== undefined) {
        setBankNiftyPrice(typeof msg.last_price === 'number' ? msg.last_price.toFixed(2) : String(msg.last_price));
      }
    });

    // Set timeout to show warning if no data received after 10 seconds
    const timeoutId = setTimeout(() => {
      console.warn('Market data not received yet. Make sure Zerodha is connected and market is open.');
    }, 10000);

    return () => {
      clearTimeout(timeoutId);
      socket.disconnect();
    };
  }, []);

  const handleLogout = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/logout', { method: 'POST', credentials: 'include' });
      if (response.ok) {
        window.location.href = '/login';
      } else {
        console.error('Logout failed');
      }
    } catch (error) {
      console.error('Error during logout:', error);
      // Even if API call fails, redirect to login
      window.location.href = '/login';
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return (
          <DashboardContent
            niftyPrice={niftyPrice}
            bankNiftyPrice={bankNiftyPrice}
            balance={balance}
            access_token={accessToken}
            onViewLiveStrategy={handleViewLiveStrategy}
            onViewChart={handleViewChart} // This will be passed down to TickDataContent eventually
          />
        );
      case 'backtest':
        return <BacktestContent />;
      case 'market-replay':
        return <MarketReplayContent />;
      case 'tick-data':
        return <TickDataContent onViewChart={handleViewChart} />;
      case 'chat':
        return <ChartContent />;
      default:
        return (
          <DashboardContent
            niftyPrice={niftyPrice}
            bankNiftyPrice={bankNiftyPrice}
            balance={balance}
            access_token={accessToken}
            onViewLiveStrategy={handleViewLiveStrategy}
            onViewChart={handleViewChart}
          />
        );
    }
  };

  return (
    <Layout navigation={
      <Navigation
        activeTab={activeTab}
        onTabChange={setActiveTab}
        userName={userName}
        onLogout={handleLogout}
      />
    }>
      {renderContent()}
      <ChartModal
        show={showChartModal}
        onClose={handleCloseChartModal}
        instrumentToken={chartInstrumentToken}
      />
      {liveStrategyId && (
        <EnhancedRealTimeStrategyMonitor
          strategyId={liveStrategyId}
          onClose={handleCloseLiveStrategyModal}
        />
      )}
    </Layout>
  );
};

export default Dashboard;
