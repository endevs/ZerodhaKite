import React, { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
  navigation?: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children, navigation }) => {
  return (
    <div className="min-vh-100 d-flex flex-column" style={{ backgroundColor: '#f8f9fa' }}>
      {navigation}
      <main className="flex-grow-1 container-fluid py-4">
        <div className="container-xxl">
          {children}
        </div>
      </main>
      <footer className="bg-dark text-light text-center py-3 mt-auto">
        <div className="container">
          <p className="mb-0">&copy; 2025 ZerodhaKite Trading Platform. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
