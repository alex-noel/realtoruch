import { api, getSessionRevision, getSessionState } from "./api";
import { disablePush } from "./pushClient";

export function completedAccountAction(revision: number) {
  return getSessionRevision() === revision + 1 && ["signed-out", "storage-cleanup"].includes(getSessionState());
}

export async function signOutWithPush(owner?: string): Promise<string | null> {
  const revision = getSessionRevision();
  let warning = "";
  try { await disablePush(owner); }
  catch { warning = " Device alert removal could not be confirmed. You can disable alerts in device settings."; }
  // Push cleanup can outlive the account that initiated sign out.
  if (getSessionRevision() !== revision) return null;
  await api.signOut();
  return completedAccountAction(revision) ? "Signed out." + warning : null;
}
