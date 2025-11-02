import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './index.css';
import App from './App'; // Keep App for now, we can refactor later if needed
import Login from './components/Login';
import Signup from './components/Signup';
import Welcome from './components/Welcome';
import Dashboard from './components/Dashboard';
import VerifyOtp from './components/VerifyOtp'; // Import VerifyOtp
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/welcome" element={<Welcome />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/verify-otp" element={<VerifyOtp />} /> {/* Add VerifyOtp route */}
        {/* Add other routes here as needed */}
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);

reportWebVitals();
