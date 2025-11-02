import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Layout from './Layout';

const VerifyOtp: React.FC = () => {
  const [otp, setOtp] = useState<string>('');
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email || '';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);

    try {
      const response = await fetch('http://localhost:8000/api/verify_otp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ email, otp }),
      });

      const data = await response.json();

      if (response.ok) {
        if (data.status === 'success') {
          setMessage({ type: 'success', text: data.message || 'OTP verified successfully!' });
          if (data.redirect) {
            navigate(data.redirect);
          } else {
            navigate('/welcome'); // Fallback if no redirect is provided
          }
        } else {
          setMessage({ type: 'danger', text: data.message || 'OTP verification failed.' });
        }
      } else {
        setMessage({ type: 'danger', text: data.message || 'OTP verification failed.' });
      }
    } catch (error) {
      console.error('Error during OTP verification:', error);
      setMessage({ type: 'danger', text: 'An unexpected error occurred. Please try again.' });
    }
  };

  return (
    <Layout>
      <div className="row justify-content-center">
        <div className="col-md-6">
          <div className="card mt-5">
            <div className="card-body">
              <h3 className="card-title text-center">Verify OTP</h3>
              {message && (
                <div className={`alert alert-${message.type}`}>
                  {message.text}
                </div>
              )}
              <form onSubmit={handleSubmit}>
                <div className="form-group mb-3">
                  <label htmlFor="email">Email Address</label>
                  <input
                    type="email"
                    className="form-control"
                    id="email"
                    name="email"
                    value={email}
                    readOnly
                  />
                </div>
                <div className="form-group mb-3">
                  <label htmlFor="otp">OTP</label>
                  <input
                    type="text"
                    className="form-control"
                    id="otp"
                    name="otp"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn btn-primary btn-block w-100">Verify</button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default VerifyOtp;
