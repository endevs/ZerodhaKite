import React, { useState } from 'react';
import axios from 'axios';

const Onboarding = () => {
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [credentialsSet, setCredentialsSet] = useState(false);

  const handleSetCredentials = () => {
    axios.post('/api/set-credentials', {
      api_key: apiKey,
      api_secret: apiSecret,
    })
    .then(response => {
      if (response.data.status === 'success') {
        setCredentialsSet(true);
      }
    })
    .catch(error => {
      console.error('Error setting credentials:', error);
    });
  };

  const handleLogin = () => {
    window.location.href = '/login';
  };

  return (
    <div>
      <h1>Welcome to the Algorithmic Trading Platform</h1>
      {!credentialsSet ? (
        <div>
          <p>Please enter your Zerodha Kite API credentials to get started.</p>
          <input
            type="text"
            placeholder="API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <input
            type="password"
            placeholder="API Secret"
            value={apiSecret}
            onChange={(e) => setApiSecret(e.target.value)}
          />
          <button onClick={handleSetCredentials}>Set Credentials</button>
        </div>
      ) : (
        <div>
          <p>Your credentials have been set. Please log in with Zerodha.</p>
          <button onClick={handleLogin}>Login with Zerodha Kite</button>
        </div>
      )}
    </div>
  );
};

export default Onboarding;
