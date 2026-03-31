import { useState } from 'react';
import { AuthLayout } from '../components/AuthLayout';
import { AUTH_ENDPOINTS } from '../config/api';
import { AuthStatus } from '../types/auth';

const BENEFITS = [
  'Быстрый разбор откликов по воронке подбора',
  'Единая панель по кандидатам и вакансиям',
  'Фокус на релевантных откликах и рисках потери кандидата',
  'Безопасное подключение только через официальный OAuth HeadHunter',
];

export function HhLoginPage() {
  const [status, setStatus] = useState<AuthStatus>('idle');

  const handleHhLogin = () => {
    setStatus('loading');
    window.location.assign(AUTH_ENDPOINTS.hhLogin);
  };

  return (
    <AuthLayout>
      <header className="auth-header">
        <h1>Вход в сервис подбора кандидатов</h1>
        <p>
          Подключите аккаунт работодателя HeadHunter и анализируйте отклики в одном
          месте
        </p>
      </header>

      <button
        type="button"
        className="primary-button"
        onClick={handleHhLogin}
        disabled={status === 'loading'}
      >
        {status === 'loading' ? 'Переходим в HeadHunter...' : 'Войти через HeadHunter'}
      </button>

      <p className="auth-disclaimer">
        Мы используем только официальный API HeadHunter. Логин и пароль от hh.ru не
        хранятся в системе.
      </p>

      <section className="auth-info-block">
        <h2>Как выполняется вход</h2>
        <p>
          Авторизация проходит через защищённый OAuth-поток HeadHunter. Доступ к данным
          получает только авторизованный работодатель.
        </p>
      </section>

      <section className="auth-benefits">
        <h2>Преимущества сервиса</h2>
        <ul>
          {BENEFITS.map((benefit) => (
            <li key={benefit}>{benefit}</li>
          ))}
        </ul>
      </section>
    </AuthLayout>
  );
}
