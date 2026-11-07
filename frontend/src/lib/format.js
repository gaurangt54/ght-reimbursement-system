// Display helpers. The API sends amounts as strings ("8000.00"); we only convert to
// Number for display, never for arithmetic that matters (the backend owns the maths).

const money = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
});

export function formatMoney(value, currency = "INR") {
    if (value === null || value === undefined || value === "") return "-";
    if (currency !== "INR") {
        return new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency,
        }).format(Number(value));
    }
    return money.format(Number(value));
}

// "2026-11-08" -> "8 Nov 2026" (parsed as a calendar date, so no timezone shift)
export function formatDate(isoDate) {
    if (!isoDate) return "-";
    const [y, m, d] = isoDate.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
    });
}

export function formatDateTime(isoDateTime) {
    if (!isoDateTime) return "-";
    return new Date(isoDateTime).toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

export function todayIso() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export const STATUS_META = {
    DRAFT: { label: "Draft", tone: "neutral" },
    SUBMITTED: { label: "Submitted", tone: "info" },
    APPROVED: { label: "Approved", tone: "success" },
    REJECTED: { label: "Rejected", tone: "danger" },
    PAID: { label: "Paid", tone: "paid" },
};

export const ACTION_LABELS = {
    created: "Draft created",
    edited: "Edited",
    deleted: "Draft deleted",
    submitted: "Submitted for approval",
    resubmitted: "Corrected and resubmitted",
    withdrawn: "Withdrawn back to draft",
    approved: "Approved",
    partially_approved: "Partially approved",
    rejected: "Rejected",
    paid: "Marked as paid",
};

export function initials(name = "") {
    return name
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0].toUpperCase())
        .join("");
}

// "3 days ago", "today" - how long a claim has been waiting
export function formatAgo(isoDateTime) {
    if (!isoDateTime) return "";
    const days = Math.floor(
        (Date.now() - new Date(isoDateTime).getTime()) / 86400000,
    );
    if (days <= 0) return "today";
    return days === 1 ? "1 day ago" : `${days} days ago`;
}
