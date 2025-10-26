import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Dashboard = () => {
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    axios.get('/api/profile')
      .then(response => {
        setProfile(response.data);
      })
      .catch(error => {
        console.error('Error fetching profile data:', error);
      });
  }, []);

  if (!profile) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>Welcome, {profile.user_name}</h1>
      <p>Your email: {profile.email}</p>
      <section className="strategy-config">
        <h2>Strategy Configuration (ORB)</h2>
        <form>
          <label>
            Candle Time Frame:
            <select>
              <option value="5">5 minutes</option>
              <option value="15">15 minutes</option>
              <option value="30">30 minutes</option>
            </select>
          </label>
          <label>
            Start Time:
            <input type="time" />
          </label>
          <label>
            End Time:
            <input type="time" />
          </label>
          <label>
            Quantity:
            <input type="number" />
          </label>
          <label>
            Stop Loss:
            <input type="number" />
          </label>
          <label>
            Target Profit:
            <input type="number" />
          </label>
          <label>
            Trailing Stop Loss:
            <input type="number" />
          </label>
          <button type="submit">Start Execution</button>
        </form>
        <div>
          <h3>About ORB Strategy</h3>
          <p>
            The Open Range Breakout (ORB) strategy is a simple yet effective
            intraday trading strategy. It involves identifying the high and
            low of a specific period (the "opening range") and placing
            buy and sell orders when the price breaks out of this range.
          </p>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
