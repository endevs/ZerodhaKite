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

// Dashboard component
const Dashboard = () => {
  const [profile, setProfile] = useState<Profile | null>(null);

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

  return (
    <div className="App">
      <header className="App-header">
        <h1>Dashboard</h1>
        {profile ? (
          <div>
            <p>Welcome, {profile.user_name}!</p>
            <p>Available Balance: {profile.equity.available.margin}</p>
          </div>
        ) : (
          <p>Loading profile...</p>
        )}
        <Link to="/">Logout</Link>
      </header>
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
