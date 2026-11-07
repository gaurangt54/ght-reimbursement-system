import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/api'
import { useToast } from '../hooks/useToast'
import { errorMessage } from '../lib/errors'
import { formatMoney } from '../lib/format'
import { ConfirmDialog } from './ConfirmDialog'

// Buttons the owner of a claim sees. Which ones appear comes from the server
// (claim.allowed_actions), so the rules live in exactly one place.
// onChanged(updatedClaim) after success; onChanged(null) means "reload, it changed under us".
export function EmployeeActions({ claim, onChanged }) {
  const toast = useToast()
  const navigate = useNavigate()
  const [dialog, setDialog] = useState(null) // 'submit' | 'withdraw' | 'delete'
  const [busy, setBusy] = useState(false)
  const can = (action) => claim.allowed_actions.includes(action)
  const resubmitting = claim.status === 'REJECTED'

  async function run(kind) {
    setBusy(true)
    try {
      if (kind === 'submit') {
        const updated = await api.submitClaim(claim.id, claim.version)
        toast.success(resubmitting ? 'Claim resubmitted for approval.' : 'Claim submitted for approval.')
        onChanged(updated)
      } else if (kind === 'withdraw') {
        const updated = await api.withdrawClaim(claim.id, claim.version)
        toast.success('Claim withdrawn. It is a draft again.')
        onChanged(updated)
      } else {
        await api.deleteClaim(claim.id, claim.version)
        toast.success('Draft deleted.')
        navigate('/claims', { replace: true })
      }
    } catch (err) {
      toast.error(errorMessage(err))
      if (err.status === 409) onChanged(null) // someone changed it: show the latest state
    } finally {
      setBusy(false)
      setDialog(null)
    }
  }

  const hasAny = ['edit', 'delete', 'submit', 'withdraw'].some(can)
  if (!hasAny) return null

  return (
    <>
      <div className="row">
        {can('delete') && (
          <button type="button" className="btn btn-ghost btn-danger-text" onClick={() => setDialog('delete')}>
            Delete
          </button>
        )}
        {can('withdraw') && (
          <button type="button" className="btn btn-secondary" onClick={() => setDialog('withdraw')}>
            Withdraw
          </button>
        )}
        {can('edit') && (
          <Link className="btn btn-secondary" to={`/claims/${claim.id}/edit`}>
            {resubmitting ? 'Edit' : 'Edit draft'}
          </Link>
        )}
        {can('submit') && (
          <button type="button" className="btn btn-primary" onClick={() => setDialog('submit')}>
            {resubmitting ? 'Resubmit' : 'Submit for approval'}
          </button>
        )}
      </div>

      {dialog === 'submit' && (
        <ConfirmDialog
          title={resubmitting ? 'Resubmit this claim?' : 'Submit for approval?'}
          confirmLabel={resubmitting ? 'Resubmit' : 'Submit'}
          busy={busy}
          onConfirm={() => run('submit')}
          onCancel={() => setDialog(null)}
        >
          <p>
            “{claim.title}” for {formatMoney(claim.amount, claim.currency)} will go to an approver.
            You can’t edit it while it is waiting, but you can withdraw it.
          </p>
        </ConfirmDialog>
      )}
      {dialog === 'withdraw' && (
        <ConfirmDialog
          title="Withdraw this claim?"
          confirmLabel="Withdraw"
          busy={busy}
          onConfirm={() => run('withdraw')}
          onCancel={() => setDialog(null)}
        >
          <p>The claim goes back to draft so you can edit it. You’ll need to submit it again.</p>
        </ConfirmDialog>
      )}
      {dialog === 'delete' && (
        <ConfirmDialog
          title="Delete this draft?"
          confirmLabel="Delete"
          tone="danger"
          busy={busy}
          onConfirm={() => run('delete')}
          onCancel={() => setDialog(null)}
        >
          <p>“{claim.title}” will be removed from your claims.</p>
        </ConfirmDialog>
      )}
    </>
  )
}