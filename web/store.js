/* Persistent key/value storage for the web app (IndexedDB), with everything cached in memory after start so that
 * the API stays synchronous inside. Falls back to memory only when IndexedDB is unavailable (private mode). */
const DB_NAME = "eurojackpot-analyzer", STORE = "kv";

function open() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("no indexedDB"));
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function openStore() {
  const cache = new Map();
  let db = null;
  try {
    db = await open();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly"), req = tx.objectStore(STORE).openCursor();
      req.onsuccess = () => { const c = req.result; if (c) { cache.set(c.key, c.value); c.continue(); } else resolve(); };
      req.onerror = () => reject(req.error);
    });
  } catch (e) { db = null; }
  // ask the browser not to evict our data when storage is tight (also the "installed web app" case)
  try { if (typeof navigator !== "undefined" && navigator.storage && navigator.storage.persist) navigator.storage.persist(); } catch (e) { /* ignore */ }
  const writes = [];
  return {
    persistent: !!db,
    get: (k, dflt = null) => (cache.has(k) ? cache.get(k) : dflt),
    set(k, v) {
      cache.set(k, v);
      if (!db) return Promise.resolve();
      const p = new Promise((resolve) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put(v, k);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
        tx.onabort = () => resolve();
      });
      writes.push(p);
      return p;
    },
    flush: () => Promise.all(writes.splice(0)),
  };
}
