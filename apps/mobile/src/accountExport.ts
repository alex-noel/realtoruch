import { Directory, File, Paths } from "expo-file-system";
import { isAvailableAsync, shareAsync } from "expo-sharing";
let sharing = false;

export async function deliverAccountExport(data: Record<string, unknown>, isCurrent: () => boolean) {
  if (sharing) throw new Error("An export share sheet is already open. Close it before trying again.");
  sharing = true;
  let directory: Directory | undefined;
  try {
    if (!await isAvailableAsync()) throw new Error("File sharing is unavailable on this device. Use the web app to download your data.");
    if (!isCurrent()) return;
    directory = new Directory(Paths.cache, "realtoruch-account-export");
    // Remove a previous file left by an interrupted app process before exporting.
    if (directory.exists) directory.delete();
    directory.create();
    const file = new File(directory, `realtoruch-account-${new Date().toISOString().slice(0, 10)}.json`);
    file.create();
    await file.write(JSON.stringify(data));
    if (!isCurrent()) return;
    await shareAsync(file.uri, { mimeType: "application/json", UTI: "public.json", dialogTitle: "Save or share your account data" });
  } catch (error) {
    if (error instanceof Error && /^(File sharing is unavailable|An export share sheet)/.test(error.message)) throw error;
    throw new Error("Could not save or share your export. Try again.");
  } finally {
    sharing = false;
    try { if (directory?.exists) directory.delete(); }
    catch { throw new Error("Could not remove the temporary export. Close and reopen the app before exporting again."); }
  }
}
