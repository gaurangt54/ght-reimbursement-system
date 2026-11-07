// One readable sentence for any error, including per-field validation errors
// (the backend's generic "fix the highlighted fields" is not useful in a toast).
export function errorMessage(err) {
    const fieldMessages = Object.values(err?.fields ?? {})
    if (fieldMessages.length > 0) return fieldMessages.join(' ')
    return err?.message ?? 'Something went wrong. Please try again.'
  }