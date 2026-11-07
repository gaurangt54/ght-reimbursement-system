// A labelled form control with an error message (or hint) underneath.
// `name` must match the id of the control inside, so the label and error are linked to it.
export function Field({ label, name, error, hint, className = '', children }) {
    return (
      <div className={`field ${error ? 'field-invalid' : ''} ${className}`}>
        <label htmlFor={name}>{label}</label>
        {children}
        {error ? (
          <div className="field-error" id={`${name}-error`} role="alert">{error}</div>
        ) : (
          hint && <div className="hint">{hint}</div>
        )}
      </div>
    )
  }