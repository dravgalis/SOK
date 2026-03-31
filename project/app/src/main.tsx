import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';

function LoginPage() {
  return (
    <main className="page">
      <section className="card">
        <h1>Вход в HR SaaS</h1>
        <p>Подключите аккаунт работодателя HeadHunter для работы с кандидатами.</p>
        <button type="button" className="cta-button">
          Войти через HeadHunter
        </button>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <LoginPage />
  </React.StrictMode>
);
