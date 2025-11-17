export async function deliverAccountExport(data: Record<string, unknown>, isCurrent: () => boolean) {
  if (!isCurrent()) return;
  const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  try {
    anchor.href = url; anchor.download = `realtoruch-account-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.style.display = "none"; document.body.appendChild(anchor); anchor.click();
  } finally {
    anchor.remove();
    // Give the browser a turn to accept the download before revoking its URL.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
