export function safeNum(v) {
    if (v == null || v === '') return null;
    const n = typeof v === 'number' ? v : Number(v);
    return Number.isFinite(n) ? n : null;
}

export function formatFixed(v, digits = 3, fallback = '-') {
    const n = safeNum(v);
    return n === null ? fallback : n.toFixed(digits);
}
