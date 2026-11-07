// One function per backend endpoint, so components never build URLs by hand.
import { download, refreshSession, request, requestWithCsrf } from './client'

const withVersion = (expectedVersion) =>
  expectedVersion === undefined ? undefined : { expected_version: expectedVersion }

export const api = {
  // ---- auth (JWT access token in memory + HttpOnly refresh cookie) ----
  login: (email, password) => request('POST', '/api/auth/login', { body: { email, password } }),
  refresh: () => refreshSession(),
  me: () => request('GET', '/api/auth/me'),
  logout: () => requestWithCsrf('POST', '/api/auth/logout'),
  changePassword: (currentPassword, newPassword) =>
    request('POST', '/api/auth/change-password', {
      body: { current_password: currentPassword, new_password: newPassword },
    }),

  // ---- users (approver-only directory, e.g. the employee filter) ----
  listEmployees: (signal) => request('GET', '/api/users', { params: { role: 'employee' }, signal }),

  // ---- config the form needs (categories, limits) ----
  getMeta: () => request('GET', '/api/meta'),

  // ---- claims ----
  listClaims: (params, signal) => request('GET', '/api/claims', { params, signal }),
  getSummary: (signal) => request('GET', '/api/claims/summary', { signal }),
  getClaim: (id, signal) => request('GET', `/api/claims/${id}`, { signal }),
  createClaim: (body) => request('POST', '/api/claims', { body }),
  updateClaim: (id, body) => request('PUT', `/api/claims/${id}`, { body }),
  deleteClaim: (id, expectedVersion) =>
    request('DELETE', `/api/claims/${id}`, { params: { expected_version: expectedVersion } }),

  // ---- lifecycle actions (pass the version you saw, to catch stale pages) ----
  submitClaim: (id, version) =>
    request('POST', `/api/claims/${id}/submit`, { body: withVersion(version) }),
  withdrawClaim: (id, version) =>
    request('POST', `/api/claims/${id}/withdraw`, { body: withVersion(version) }),
  approveClaim: (id, { approvedAmount, comment, version }) =>
    request('POST', `/api/claims/${id}/approve`, {
      body: { approved_amount: approvedAmount, comment, expected_version: version },
    }),
  rejectClaim: (id, { comment, version }) =>
    request('POST', `/api/claims/${id}/reject`, { body: { comment, expected_version: version } }),
  payClaim: (id, { paymentReference, version }) =>
    request('POST', `/api/claims/${id}/pay`, {
      body: { payment_reference: paymentReference, expected_version: version },
    }),

  exportCsv: (params) => download('/api/claims/export.csv', { params, filename: 'claims.csv' }),
}