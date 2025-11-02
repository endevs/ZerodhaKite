import React, { useState, useEffect, useCallback } from 'react';
import Layout from './Layout';
import Navigation from './Navigation';
import { io, Socket } from 'socket.io-client';
import DashboardContent from './DashboardContent';
import BacktestContent from './BacktestContent';
import MarketReplayContent from './MarketReplayContent';
import TickDataContent from './TickDataContent';
import ChartModal from './ChartModal';
import LiveStrategyModal from './LiveStrategyModal';

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

    fetchUserData();

    const socket: Socket = io('http://localhost:8000'); // Connect directly to backend for socket.io

    socket.on('connect', () => {
      console.log('Connected to WebSocket');
      socket.emit('my_event', { data: 'I\'m connected!' });
    });

    socket.on('unauthorized', (msg: { message: string }) => {
      alert(msg.message);
      window.location.href = 'http://localhost:8000/api/logout'; // Redirect to logout or login page
    });

    socket.on('market_data', (msg: { nifty_price: string; banknifty_price: string }) => {
      if (msg.nifty_price) {
        setNiftyPrice(msg.nifty_price);
      }
      if (msg.banknifty_price) {
        setBankNiftyPrice(msg.banknifty_price);
      }
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const handleLogout = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/logout', { method: 'POST', credentials: 'include' });
      if (response.ok) {
        window.location.href = 'http://localhost:8000/api/';
      } else {
        console.error('Logout failed');
      }
    } catch (error) {
      console.error('Error during logout:', error);
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
      <LiveStrategyModal
        show={showLiveStrategyModal}
        onClose={handleCloseLiveStrategyModal}
        strategyId={liveStrategyId}
      />
    </Layout>
  );
};

export default Dashboard;
