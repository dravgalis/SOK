import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { APP_ENDPOINTS, APP_ROUTES } from '../config';

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1200;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function PaymentReturnPage() {
  const navigate = useNavigate();
  const [statusText, setStatusText] = useState('Проверяем статус оплаты...');

  useEffect(() => {
    const verifyBilling = async () => {
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt += 1) {
        const response = await fetch(APP_ENDPOINTS.billingMe, { credentials: 'include' });

        if (response.ok) {
          navigate(APP_ROUTES.app, { replace: true });
          return;
        }

        if (response.status !== 401) {
          setStatusText('Не удалось проверить оплату. Попробуйте обновить страницу.');
          return;
        }

        if (attempt < MAX_RETRIES) {
          setStatusText(`Проверяем авторизацию (${attempt}/${MAX_RETRIES})...`);
          await sleep(RETRY_DELAY_MS);
          continue;
        }
      }

      navigate(APP_ROUTES.login, { replace: true });
    };

    void verifyBilling();
  }, [navigate]);

  return (
    <main className="page page-top">
      <section className="card dashboard-card">
        <p>{statusText}</p>
      </section>
    </main>
  );
}
