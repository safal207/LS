import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/global.css';
import './i18n';
import IndexPage from './pages/index';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <IndexPage />
  </React.StrictMode>
);
