import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';

// main.tsx -add dark class to html element on load
if (localStorage.getItem('theme') !== 'light') {
  document.documentElement.classList.add('dark');
}

// Handle impersonation token receiving from the Super Admin parent window
if (window.opener && !sessionStorage.getItem('Frixel Connect_impersonation_token')) {
  const handleImpersonationToken = (event: MessageEvent) => {
    if (event.origin === window.location.origin && event.data?.type === 'impersonation_token') {
      sessionStorage.setItem('Frixel Connect_impersonation_token', event.data.token);
      window.removeEventListener('message', handleImpersonationToken);
      window.location.reload();
    }
  };
  window.addEventListener('message', handleImpersonationToken);
  window.opener.postMessage('impersonation_ready', window.location.origin);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);

