import { render, screen } from '@testing-library/react';
import App from './App';

test('renders onboarding heading', () => {
  render(<App />);
  const headingElement = screen.getByText(/Welcome to the Algorithmic Trading Platform/i);
  expect(headingElement).toBeInTheDocument();
});
