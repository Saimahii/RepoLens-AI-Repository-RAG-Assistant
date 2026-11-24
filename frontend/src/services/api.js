// Axios API client for the RepoLens FastAPI backend.
// Base URL comes from frontend/.env (REACT_APP_API_URL).

import axios from 'axios';

export const API_BASE_URL =
  (process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // allow enough time for git clones and LLM responses
  headers: {
    'Content-Type': 'application/json',
  },
});

// Turn Axios/FastAPI errors into a single readable message for the UI
export function extractErrorMessage(error, fallback = 'Something went wrong.') {
  if (error?.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  }
  if (error?.code === 'ECONNABORTED') {
    return 'Request timed out. Please try again.';
  }
  if (error?.message === 'Network Error') {
    return `Could not reach the backend at ${API_BASE_URL}. Make sure uvicorn is running.`;
  }
  return error?.message || fallback;
}

// ── Health endpoint ──

export async function checkHealth() {
  const { data } = await api.get('/health', { timeout: 5000 });
  return data; // { status, database }
}

// ── Repository endpoints ──

export async function uploadRepo(githubUrl) {
  const { data } = await api.post('/repo/upload', { github_url: githubUrl });
  return data; // { repo_id, status }
}

export async function indexRepo(repoId) {
  const { data } = await api.post('/repo/index', { repo_id: repoId });
  return data; // { repo_id, status }
}

export async function getRepoStatus(repoId) {
  const { data } = await api.get(`/repo/status/${repoId}`);
  return data; // { status, step, error }
}

export async function getRepoFiles(repoId) {
  const { data } = await api.get('/repo/files', { params: { repo_id: repoId } });
  return data; // [{ name, path, type, language, children }]
}

export async function getRepoFile(repoId, path) {
  const { data } = await api.get('/repo/file', { params: { repo_id: repoId, path } });
  return data; // { path, language, content }
}

// ── Chat endpoints ──

export async function askChat({ repoId, sessionId, question, filters }) {
  const payload = {
    repo_id: repoId,
    question,
  };
  if (sessionId) {
    payload.session_id = sessionId;
  }
  const cleanFilters = {};
  if (filters?.language) cleanFilters.language = filters.language;
  if (filters?.path_prefix?.trim()) cleanFilters.path_prefix = filters.path_prefix.trim();
  if (Object.keys(cleanFilters).length > 0) {
    payload.filters = cleanFilters;
  }

  const { data } = await api.post('/chat/ask', payload);
  return data; // { session_id, agent, answer, sources }
}

export async function getChatSessions(repoId) {
  const { data } = await api.get('/chat/sessions', { params: { repo_id: repoId } });
  return data; // [{ id, repository_id, title, created_at }]
}

export async function getChatHistory(sessionId) {
  const { data } = await api.get('/chat/history', { params: { session_id: sessionId } });
  return data; // [{ id, session_id, role, content, agent, sources, created_at }]
}

export default api;
