import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('fleet_owner_user');
    return saved ? JSON.parse(saved) : null;
  });

  const login = (email, password) => {
    if (email === 'admin@driversafety.com' && password === 'admin123') {
      const userData = {
        email: 'admin@driversafety.com',
        name: 'Fleet Administrator',
        role: 'OWNER',
        company: 'Vanguard Transport Services'
      };
      setUser(userData);
      localStorage.setItem('fleet_owner_user', JSON.stringify(userData));
      return { success: true };
    }
    return { success: false, error: 'Invalid email or password' };
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('fleet_owner_user');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
