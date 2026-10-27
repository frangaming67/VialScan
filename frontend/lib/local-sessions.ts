import type { ScanSession } from "./types";

const DATABASE_NAME = "vialscan-local";
const STORE_NAME = "sessions";
const DATABASE_VERSION = 1;

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Este navegador no permite guardar análisis locales."));
      return;
    }
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("No se pudo abrir el almacenamiento local."));
  });
}

export async function loadLocalSessions(): Promise<ScanSession[]> {
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const request = database.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).getAll();
      request.onsuccess = () => resolve((request.result as ScanSession[]).sort((a, b) =>
        (b.started_at ?? "").localeCompare(a.started_at ?? "")));
      request.onerror = () => reject(request.error ?? new Error("No se pudieron cargar los análisis locales."));
    });
  } finally {
    database.close();
  }
}

export async function saveLocalSession(session: ScanSession): Promise<void> {
  const database = await openDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).put(session);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error("No se pudo guardar el análisis local."));
      transaction.onabort = () => reject(transaction.error ?? new Error("Se canceló el guardado local."));
    });
  } finally {
    database.close();
  }
}
