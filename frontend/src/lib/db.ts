import { openDB, type DBSchema } from "idb";
import type { ScanRecord } from "../types";

const DB_NAME = "dawaicheck_history";
const STORE = "scans";
const MAX_SAVED = 20;

interface DawaiCheckDB extends DBSchema {
  scans: {
    key: string;
    value: ScanRecord;
    indexes: { "by-created": string };
  };
}

function database() {
  return openDB<DawaiCheckDB>(DB_NAME, 1, {
    upgrade(db) {
      const store = db.createObjectStore(STORE, { keyPath: "id" });
      store.createIndex("by-created", "createdAt");
    },
  });
}

export async function saveScan(record: ScanRecord): Promise<void> {
  const db = await database();
  await db.put(STORE, record);
  const all = await db.getAllFromIndex(STORE, "by-created");
  const excess = all.length - MAX_SAVED;
  if (excess > 0) {
    const oldest = all.slice(0, excess);
    const tx = db.transaction(STORE, "readwrite");
    await Promise.all(oldest.map((item) => tx.store.delete(item.id)));
    await tx.done;
  }
}

export async function listScans(): Promise<ScanRecord[]> {
  const db = await database();
  const records = await db.getAllFromIndex(STORE, "by-created");
  return records.reverse();
}

export async function getScan(id: string): Promise<ScanRecord | undefined> {
  const db = await database();
  return db.get(STORE, id);
}

export async function deleteScan(id: string): Promise<void> {
  const db = await database();
  await db.delete(STORE, id);
}

export async function clearScans(): Promise<void> {
  const db = await database();
  await db.clear(STORE);
}

export async function deleteAllLocalData(): Promise<void> {
  await clearScans();
  try {
    const keys: string[] = [];
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (key?.startsWith("dawaiicheck_")) keys.push(key);
    }
    for (const key of keys) window.localStorage.removeItem(key);
  } catch {
    // Ignore storage restrictions while deleting.
  }
}
