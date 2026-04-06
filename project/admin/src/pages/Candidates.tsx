import { useEffect, useState } from 'react';
import { Candidate, fetchCandidatesFromFirstVacancy } from '../api';

export function Candidates() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchCandidatesFromFirstVacancy();
        setCandidates(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load candidates.');
      }
    }

    void load();
  }, []);

  return (
    <section>
      <h1>Candidates</h1>
      <p className="subtitle">Responses for the first available vacancy.</p>
      {error && <p className="error-text">{error}</p>}

      <article className="card">
        <ul className="list">
          {candidates.map((candidate) => (
            <li key={candidate.response_id}>
              <strong>{candidate.candidate_name ?? 'Unknown candidate'}</strong>
              <span>{candidate.resume_title ?? 'No resume title'}</span>
            </li>
          ))}
          {candidates.length === 0 && <li>No candidates available.</li>}
        </ul>
      </article>
    </section>
  );
}
