import { useState } from "react";
import { api } from "../api/api";
import { errorMessage } from "../lib/errors";
import { formatMoney } from "../lib/format";
import { validateApproval, validateRejection } from "../lib/validation";
import { Field } from "./Field";
import { Modal } from "./Modal";

// Shared by the three dialogs below.
//   run(call)   - performs the API call and handles every outcome:
//                 success  -> onDone(updatedClaim)
//                 409/404  -> onConflict(message): someone else changed (or withdrew) the claim first
//                 422/else -> errors stay inside the dialog so the approver can fix them
function useReviewCall({ onDone, onConflict }) {
    const [busy, setBusy] = useState(false);
    const [errors, setErrors] = useState({});
    const [formError, setFormError] = useState(null);

    async function run(call) {
        setBusy(true);
        setFormError(null);
        try {
            onDone(await call());
        } catch (err) {
            if (err.status === 409) {
                onConflict(errorMessage(err));
                return;
            }
            if (err.status === 404) {
                // Drafts are private, so a claim the employee just withdrew disappears for approvers.
                onConflict(
                    "This claim is no longer available. The employee may have withdrawn it.",
                );
                return;
            }
            const fields = err.fields ?? {};
            setErrors(fields);
            setFormError(
                Object.keys(fields).length > 0 ? null : errorMessage(err),
            );
            setBusy(false);
        }
    }

    return { busy, errors, setErrors, formError, run };
}

function FormError({ message }) {
    if (!message) return null;
    return (
        <div className="alert alert-error" role="alert">
            <p>{message}</p>
        </div>
    );
}

function ClaimSummary({ claim }) {
    return (
        <p className="review-summary">
            <strong>{claim.title}</strong>
            <span className="muted">
                {claim.employee.name} · {claim.category} · claimed{" "}
                {formatMoney(claim.amount, claim.currency)}
            </span>
        </p>
    );
}

// ---------- Approve (in full, or partially) ----------
export function ApproveDialog({ claim, onClose, onDone, onConflict }) {
    const { busy, errors, setErrors, formError, run } = useReviewCall({
        onDone,
        onConflict,
    });
    const [amount, setAmount] = useState(claim.amount);
    const [comment, setComment] = useState("");

    const entered = amount.trim();
    const isNumber = /^\d+(\.\d{1,2})?$/.test(entered);
    const partial =
        isNumber &&
        Number(entered) > 0 &&
        Number(entered) < Number(claim.amount);
    const notReimbursed = partial ? Number(claim.amount) - Number(entered) : 0;

    function submit(event) {
        event.preventDefault();
        const found = validateApproval({ amount, comment }, claim);
        setErrors(found);
        if (Object.keys(found).length > 0) return;
        run(() =>
            api.approveClaim(claim.id, {
                // Leave the amount out for a full approval; the server then approves what was claimed.
                approvedAmount: partial ? entered : undefined,
                comment: comment.trim() || undefined,
                version: claim.version,
            }),
        );
    }

    return (
        <Modal title="Approve claim" onClose={busy ? () => {} : onClose}>
            <form noValidate onSubmit={submit}>
                <ClaimSummary claim={claim} />
                <FormError message={formError} />

                <Field
                    label="Amount to approve (₹)"
                    name="approved_amount"
                    error={errors.approved_amount}
                    hint="Lower it to approve only part of the claim."
                >
                    <input
                        id="approved_amount"
                        className="input"
                        inputMode="decimal"
                        autoFocus
                        value={amount}
                        aria-invalid={errors.approved_amount ? true : undefined}
                        onChange={(e) => {
                            setAmount(e.target.value);
                            setErrors({
                                ...errors,
                                approved_amount: undefined,
                            });
                        }}
                    />
                </Field>

                {partial && (
                    <div className="alert alert-warn">
                        <p>
                            Partial approval:{" "}
                            {formatMoney(notReimbursed, claim.currency)} of this
                            claim will not be reimbursed. The employee will see
                            your comment.
                        </p>
                    </div>
                )}

                <Field
                    label={partial ? "Comment *" : "Comment (optional)"}
                    name="comment"
                    error={errors.comment}
                >
                    <textarea
                        id="comment"
                        className="textarea"
                        maxLength={500}
                        placeholder={
                            partial
                                ? "Why is the amount being reduced?"
                                : "Anything the employee should know"
                        }
                        value={comment}
                        aria-invalid={errors.comment ? true : undefined}
                        onChange={(e) => {
                            setComment(e.target.value);
                            setErrors({ ...errors, comment: undefined });
                        }}
                    />
                </Field>

                <div className="modal-actions">
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={onClose}
                        disabled={busy}
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={busy}
                    >
                        {busy
                            ? "Approving…"
                            : partial
                              ? "Approve partially"
                              : "Approve in full"}
                    </button>
                </div>
            </form>
        </Modal>
    );
}

// ---------- Reject (a reason is mandatory) ----------
export function RejectDialog({ claim, onClose, onDone, onConflict }) {
    const { busy, errors, setErrors, formError, run } = useReviewCall({
        onDone,
        onConflict,
    });
    const [comment, setComment] = useState("");

    function submit(event) {
        event.preventDefault();
        const found = validateRejection({ comment });
        setErrors(found);
        if (Object.keys(found).length > 0) return;
        run(() =>
            api.rejectClaim(claim.id, {
                comment: comment.trim(),
                version: claim.version,
            }),
        );
    }

    return (
        <Modal title="Reject claim" onClose={busy ? () => {} : onClose}>
            <form noValidate onSubmit={submit}>
                <ClaimSummary claim={claim} />
                <FormError message={formError} />

                <Field
                    label="Reason *"
                    name="comment"
                    error={errors.comment}
                    hint="The employee sees this, and can correct the claim and resubmit it."
                >
                    <textarea
                        id="comment"
                        className="textarea"
                        maxLength={500}
                        autoFocus
                        placeholder="What needs to change?"
                        value={comment}
                        aria-invalid={errors.comment ? true : undefined}
                        onChange={(e) => {
                            setComment(e.target.value);
                            setErrors({});
                        }}
                    />
                </Field>

                <div className="modal-actions">
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={onClose}
                        disabled={busy}
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        className="btn btn-danger"
                        disabled={busy}
                    >
                        {busy ? "Rejecting…" : "Reject claim"}
                    </button>
                </div>
            </form>
        </Modal>
    );
}

// ---------- Mark as paid ----------
export function PayDialog({ claim, onClose, onDone, onConflict }) {
    const { busy, errors, setErrors, formError, run } = useReviewCall({
        onDone,
        onConflict,
    });
    const [reference, setReference] = useState("");

    function submit(event) {
        event.preventDefault();
        run(() =>
            api.payClaim(claim.id, {
                paymentReference: reference.trim() || undefined,
                version: claim.version,
            }),
        );
    }

    return (
        <Modal title="Mark as paid" onClose={busy ? () => {} : onClose}>
            <form noValidate onSubmit={submit}>
                <ClaimSummary claim={claim} />
                <FormError message={formError} />

                <p>
                    Confirm that{" "}
                    <strong>
                        {formatMoney(claim.approved_amount, claim.currency)}
                    </strong>{" "}
                    has been paid to {claim.employee.name}. This cannot be
                    undone.
                </p>

                <Field
                    label="Payment reference (optional)"
                    name="payment_reference"
                    error={errors.payment_reference}
                    hint="e.g. bank transfer or UTR number"
                >
                    <input
                        id="payment_reference"
                        className="input"
                        maxLength={64}
                        autoFocus
                        value={reference}
                        aria-invalid={
                            errors.payment_reference ? true : undefined
                        }
                        onChange={(e) => {
                            setReference(e.target.value);
                            setErrors({});
                        }}
                    />
                </Field>

                <div className="modal-actions">
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={onClose}
                        disabled={busy}
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={busy}
                    >
                        {busy ? "Saving…" : "Mark as paid"}
                    </button>
                </div>
            </form>
        </Modal>
    );
}
