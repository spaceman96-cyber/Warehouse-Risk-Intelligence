import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

export default function UploadModal({
  open,
  onClose,
  onUploaded, // call refreshAll() from App after upload succeeds
}) {
  const [skuFile, setSkuFile] = useState(null);
  const [adjFile, setAdjFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(""); // text status
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) {
      setSkuFile(null);
      setAdjFile(null);
      setBusy(false);
      setStep("");
      setErr("");
    }
  }, [open]);

  const canSubmit = useMemo(() => !!skuFile && !!adjFile && !busy, [skuFile, adjFile, busy]);

  const upload = async () => {
    setErr("");
    setBusy(true);

    try {
      setStep("Uploading SKU master…");
      await api.uploadSkuMaster(skuFile);

      setStep("Uploading adjustments…");
      await api.uploadAdjustments(adjFile);

      setStep("Refreshing dashboard…");
      await onUploaded?.();

      setStep("");
      onClose?.();
    } catch (e) {
      setErr(e?.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div style={styles.backdrop} onMouseDown={onClose}>
      <div style={styles.modal} onMouseDown={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <div>
            <div style={styles.title}>Upload WRI Data</div>
            <div style={styles.sub}>Upload both files, then we recompute scores.</div>
          </div>
          <button style={styles.x} onClick={onClose} disabled={busy} title="Close">✕</button>
        </div>

        <div style={styles.body}>
          <div style={styles.field}>
            <label style={styles.label}>SKU Master CSV</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setSkuFile(e.target.files?.[0] || null)}
              disabled={busy}
              style={styles.input}
            />
            <div style={styles.hint}>
              Required columns (example): <code>sku_code</code>, <code>sku_name</code>, <code>category</code>…
            </div>
            {skuFile && <div style={styles.filePill}>✓ {skuFile.name}</div>}
          </div>

          <div style={styles.field}>
            <label style={styles.label}>Adjustments CSV</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setAdjFile(e.target.files?.[0] || null)}
              disabled={busy}
              style={styles.input}
            />
            <div style={styles.hint}>
              Required columns: <code>timestamp</code>, <code>sku_code</code>, <code>qty_delta</code>, <code>user_ref</code>
            </div>
            {adjFile && <div style={styles.filePill}>✓ {adjFile.name}</div>}
          </div>

          {err && <div style={styles.error}>⚠ {err}</div>}
          {busy && step && <div style={styles.step}>{step}</div>}
        </div>

        <div style={styles.footer}>
          <button style={styles.btnGhost} onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button style={{ ...styles.btnPrimary, opacity: canSubmit ? 1 : 0.5 }}
            onClick={upload}
            disabled={!canSubmit}
          >
            {busy ? "Uploading…" : "Upload & Refresh"}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.55)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 9999,
    padding: 16,
  },
  modal: {
    width: "min(720px, 100%)",
    borderRadius: 14,
    background: "var(--surface)",
    border: "1px solid var(--border)",
    boxShadow: "var(--shadow-pop)",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
    padding: "16px 18px",
    borderBottom: "1px solid var(--border)",
  },
  title: { fontSize: 15, fontWeight: 800, color: "var(--text)" },
  sub: { fontSize: 11, color: "var(--text-muted)", marginTop: 4, lineHeight: 1.4 },
  x: {
    width: 34,
    height: 34,
    borderRadius: 10,
    cursor: "pointer",
    background: "var(--bg2)",
    border: "1px solid var(--border)",
    color: "var(--text-sub)",
  },
  body: { padding: 18, display: "grid", gap: 14 },
  field: {
    padding: 14,
    borderRadius: 12,
    border: "1px solid var(--border)",
    background: "var(--bg2)",
  },
  label: { display: "block", fontSize: 12, fontWeight: 700, color: "var(--text)", marginBottom: 8 },
  input: { width: "100%" },
  hint: { fontSize: 11, color: "var(--text-muted)", marginTop: 8, lineHeight: 1.45 },
  filePill: {
    marginTop: 10,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "4px 10px",
    borderRadius: 999,
    border: "1px solid var(--border)",
    background: "var(--surface)",
    color: "var(--text-sub)",
    fontSize: 11,
    fontFamily: "monospace",
  },
  error: {
    padding: "10px 12px",
    borderRadius: 10,
    border: "1px solid rgba(248,113,113,0.28)",
    background: "rgba(248,113,113,0.10)",
    color: "var(--red)",
    fontSize: 12,
    lineHeight: 1.4,
  },
  step: {
    padding: "10px 12px",
    borderRadius: 10,
    border: "1px solid var(--border)",
    background: "var(--surface-pop)",
    color: "var(--text-sub)",
    fontSize: 12,
    fontFamily: "monospace",
  },
  footer: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 10,
    padding: "14px 18px",
    borderTop: "1px solid var(--border)",
    background: "var(--surface)",
  },
  btnGhost: {
    fontSize: 12,
    fontWeight: 600,
    padding: "8px 14px",
    borderRadius: 10,
    cursor: "pointer",
    background: "transparent",
    color: "var(--text-sub)",
    border: "1px solid var(--border)",
  },
  btnPrimary: {
    fontSize: 12,
    fontWeight: 800,
    padding: "8px 14px",
    borderRadius: 10,
    cursor: "pointer",
    background: "var(--accent)",
    color: "#000",
    border: "none",
    boxShadow: "0 2px 14px var(--accent-glow)",
  },
};