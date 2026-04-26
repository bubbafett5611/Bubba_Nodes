// IndexedDB helpers for autocomplete caches.

const DB_NAME = "bubbaAutocomplete";
const DB_VERSION = 1;
const TAG_STORE = "danbooruTags";
const TAG_KEY = "all";

let dbPromise = null;

function openAutocompleteDb() {
	if (dbPromise) {
		return dbPromise;
	}

	if (typeof indexedDB === "undefined") {
		return Promise.resolve(null);
	}

	dbPromise = new Promise((resolve, reject) => {
		const request = indexedDB.open(DB_NAME, DB_VERSION);

		request.onupgradeneeded = () => {
			const db = request.result;
			if (!db.objectStoreNames.contains(TAG_STORE)) {
				db.createObjectStore(TAG_STORE, { keyPath: "id" });
			}
		};

		request.onsuccess = () => {
			resolve(request.result);
		};

		request.onerror = () => {
			reject(request.error || new Error("Failed to open IndexedDB."));
		};
	});

	return dbPromise;
}

export async function loadDanbooruTagsFromIndexedDb() {
	try {
		const db = await openAutocompleteDb();
		if (!db) {
			return [];
		}

		return await new Promise((resolve, reject) => {
			const tx = db.transaction(TAG_STORE, "readonly");
			const store = tx.objectStore(TAG_STORE);
			const request = store.get(TAG_KEY);

			request.onsuccess = () => {
				const tags = request.result?.tags;
				resolve(Array.isArray(tags) ? tags : []);
			};

			request.onerror = () => {
				reject(request.error || new Error("Failed to read IndexedDB tags."));
			};
		});
	} catch (error) {
		console.warn("Bubba Autocomplete: failed to read IndexedDB tags", error);
		return [];
	}
}

export async function saveDanbooruTagsToIndexedDb(tags) {
	const payload = Array.isArray(tags) ? tags : [];
	const db = await openAutocompleteDb();
	if (!db) {
		return;
	}

	await new Promise((resolve, reject) => {
		const tx = db.transaction(TAG_STORE, "readwrite");
		const store = tx.objectStore(TAG_STORE);
		store.put({
			id: TAG_KEY,
			tags: payload,
			updatedAt: new Date().toISOString(),
		});

		tx.oncomplete = () => resolve();
		tx.onerror = () => reject(tx.error || new Error("Failed to write IndexedDB tags."));
		tx.onabort = () => reject(tx.error || new Error("IndexedDB transaction aborted."));
	});
}

export async function clearDanbooruTagsFromIndexedDb() {
	try {
		const db = await openAutocompleteDb();
		if (!db) {
			return;
		}

		await new Promise((resolve, reject) => {
			const tx = db.transaction(TAG_STORE, "readwrite");
			const store = tx.objectStore(TAG_STORE);
			store.delete(TAG_KEY);

			tx.oncomplete = () => resolve();
			tx.onerror = () => reject(tx.error || new Error("Failed to clear IndexedDB tags."));
			tx.onabort = () => reject(tx.error || new Error("IndexedDB clear transaction aborted."));
		});
	} catch (error) {
		console.warn("Bubba Autocomplete: failed to clear IndexedDB tags", error);
	}
}
