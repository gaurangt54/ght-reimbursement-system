import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/api'
import { useToast } from '../hooks/useToast'
import { errorMessage } from '../lib/errors'
import { formatMoney, todayIso } from '../lib/format'
import { validateClaim } from '../lib/validation'
import { Field } from './Field' 



// Create or edit a claim. `claim` is undefined when creating.
export function ClaimForm({ meta, claim, initialError }) {
  const navigate = useNavigate()
  const toast = useToast()
  const isEdit = Boolean(claim)
  const isRejected = claim?.status === 'REJECTED'

  const [values, setValues] = useState(() => ({
    title: claim?.title ?? '',
    category: claim?.category ?? '',
    amount: claim?.amount ?? '',
    expense_date: claim?.expense_date ?? todayIso(),
    receipt_ref: claim?.receipt_ref ?? '',
    description: claim?.description ?? '',
  }))
  const [version, setVersion] = useState(claim?.version)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(initialError ? { message: initialError } : null) // { message, stale }
  const [busy, setBusy] = useState(null) // null | 'save' | 'submit'

  const aria = (name) => ({
    id: name,
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': errors[name] ? `${name}-error` : undefined,
  })

  function change(name) {
    return (event) => {
      setValues((current) => ({ ...current, [name]: event.target.value }))
      if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }))
    }
  }

  async function save(andSubmit) {
    setFormError(null)
    const found = validateClaim(values, meta, { forSubmit: andSubmit })
    if (Object.keys(found).length > 0) {
      setErrors(found)
      document.getElementById(Object.keys(found)[0])?.focus()
      return
    }
    setErrors({})
    setBusy(andSubmit ? 'submit' : 'save')

    const body = {
      title: values.title.trim(),
      category: values.category,
      amount: values.amount.trim(),
      expense_date: values.expense_date,
      receipt_ref: values.receipt_ref.trim(),
      description: values.description.trim(),
    }

    let saved
    try {
      saved = isEdit
        ? await api.updateClaim(claim.id, { ...body, expected_version: version })
        : await api.createClaim(body)
      setVersion(saved.version)
    } catch (err) {
      setErrors(err.fields ?? {})
      setFormError({ message: errorMessage(err), stale: err.code === 'STALE_VERSION' })
      setBusy(null)
      return
    }

    if (!andSubmit) {
      toast.success(isEdit ? 'Changes saved.' : 'Draft saved.')
      navigate(`/claims/${saved.id}`)
      return
    }

    try {
      await api.submitClaim(saved.id, saved.version)
      toast.success(isRejected ? 'Claim resubmitted for approval.' : 'Claim submitted for approval.')
      navigate(`/claims/${saved.id}`)
    } catch (err) {
      // The claim itself was saved; only the submit step failed.
      const message = `Your changes were saved, but the claim was not submitted. ${errorMessage(err)}`
      if (!isEdit) {
        // A brand-new draft now exists: continue on its edit page and carry the message along.
        navigate(`/claims/${saved.id}/edit`, { replace: true, state: { submitError: message } })
        return
      }
      setErrors(err.fields ?? {})
      setFormError({ message })
      setBusy(null)
    }
  }

  const disabled = busy !== null

  return (
    <form
      className="card"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        save(false)
      }}
    >
      {isRejected && (
        <div className="alert alert-error">
          <p>
            <strong>Rejected{claim.reviewer ? ` by ${claim.reviewer.name}` : ''}:</strong>{' '}
            “{claim.review_comment}”
          </p>
          <p>Fix the issue below, then resubmit.</p>
        </div>
      )}

      {formError && (
        <div className="alert alert-error" role="alert">
          <p>{formError.message}</p>
          {formError.stale && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => window.location.reload()}>
              Load the latest version
            </button>
          )}
        </div>
      )}

      <div className="form-grid">
        <Field label="Title *" name="title" error={errors.title} className="full">
          <input
            {...aria('title')}
            className="input"
            maxLength={120}
            placeholder="e.g. Client lunch at Taj"
            value={values.title}
            onChange={change('title')}
          />
        </Field>

        <Field label="Category *" name="category" error={errors.category}>
          <select {...aria('category')} className="select" value={values.category} onChange={change('category')}>
            <option value="">Select a category</option>
            {meta.categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </Field>

        <Field label="Amount (₹) *" name="amount" error={errors.amount} hint={`Up to ${formatMoney(meta.max_claim_amount)} per claim`}>
          <input
            {...aria('amount')}
            className="input"
            inputMode="decimal"
            placeholder="0.00"
            value={values.amount}
            onChange={change('amount')}
          />
        </Field>

        <Field label="Expense date *" name="expense_date" error={errors.expense_date} hint={`Within the last ${meta.max_expense_age_days} days`}>
          <input
            {...aria('expense_date')}
            className="input"
            type="date"
            max={todayIso()}
            value={values.expense_date}
            onChange={change('expense_date')}
          />
        </Field>

        <Field
          label="Receipt / invoice reference"
          name="receipt_ref"
          error={errors.receipt_ref}
          hint={`Required to submit claims above ${formatMoney(meta.receipt_required_above)}`}
        >
          <input
            {...aria('receipt_ref')}
            className="input"
            maxLength={200}
            placeholder="Invoice number or link"
            value={values.receipt_ref}
            onChange={change('receipt_ref')}
          />
        </Field>

        <Field label="Description" name="description" error={errors.description} className="full">
          <textarea
            {...aria('description')}
            className="textarea"
            maxLength={1000}
            placeholder="What was this expense for?"
            value={values.description}
            onChange={change('description')}
          />
        </Field>
      </div>

      <div className="row form-actions">
        <Link className="btn btn-ghost" to={isEdit ? `/claims/${claim.id}` : '/claims'}>
          Cancel
        </Link>
        <span className="spacer" />
        <button type="submit" className="btn btn-secondary" disabled={disabled}>
          {busy === 'save' ? 'Saving…' : isEdit ? 'Save changes' : 'Save as draft'}
        </button>
        <button type="button" className="btn btn-primary" disabled={disabled} onClick={() => save(true)}>
          {busy === 'submit' ? 'Submitting…' : isRejected ? 'Save & resubmit' : 'Save & submit'}
        </button>
      </div>
    </form>
  )
}