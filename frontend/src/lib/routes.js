// Where each role lands after login, and the role names the backend uses.
export const ROLES = { EMPLOYEE: 'employee', APPROVER: 'approver' }

export function homePathFor(user) {
  return user?.role === ROLES.APPROVER ? '/review' : '/claims'
}