import { useState } from 'react'
import { useToast } from '../hooks/useToast'
import { formatMoney } from '../lib/format'
import { ApproveDialog, PayDialog, RejectDialog } from './ReviewDialogs'

const SUCCESS = {
  approve: (claim, updated) =>
    updated.is_partial
      ? `Partially approved: ${formatMoney(updated.approved_amount, updated.currency)} of ${formatMoney(claim.amount, claim.currency)}.`
      : 'Claim approved in full.',
  reject: () => 'Claim rejected. The employee can correct and resubmit it.',
  pay: () => 'Marked as paid.',
}

// Buttons an approver sees on a claim. Which ones appear comes from the server
// (claim.allowed_actions): it already accounts for the status and for "not your own claim".
// onChanged(updatedClaim) after success; onChanged(null) means "reload, it changed under us".
export function ApproverActions({ claim, onChanged }) {
  const toast = useToast()
  const [dialog, setDialog] = useState(null) // 'approve' | 'reject' | 'pay'
  const can = (action) => claim.allowed_actions.includes(action)

  function done(kind) {
    return (updated) => {
      toast.success(SUCCESS[kind](claim, updated))
      setDialog(null)
      onChanged(updated)
    }
  }

  // Someone else got there first (employee withdrew it, another approver decided it, ...).
  function conflict(message) {
    toast.error(`${message} Showing the latest version.`)
    setDialog(null)
    onChanged(null)
  }

  if (!['approve', 'reject', 'pay'].some(can)) return null

  const dialogProps = { claim, onClose: () => setDialog(null), onConflict: conflict }

  return (
    <>
      <div className="row">
        {can('reject') && (
          <button type="button" className="btn btn-secondary btn-danger-text" onClick={() => setDialog('reject')}>
            Reject
          </button>
        )}
        {can('approve') && (
          <button type="button" className="btn btn-primary" onClick={() => setDialog('approve')}>
            Approve
          </button>
        )}
        {can('pay') && (
          <button type="button" className="btn btn-primary" onClick={() => setDialog('pay')}>
            Mark as paid
          </button>
        )}
      </div>

      {dialog === 'approve' && <ApproveDialog {...dialogProps} onDone={done('approve')} />}
      {dialog === 'reject' && <RejectDialog {...dialogProps} onDone={done('reject')} />}
      {dialog === 'pay' && <PayDialog {...dialogProps} onDone={done('pay')} />}
    </>
  )
}