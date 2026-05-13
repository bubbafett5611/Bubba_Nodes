export function readStringArray(key) {
	const raw = localStorage.getItem(key);
	if (!raw) {
		return [];
	}
	try {
		const parsed = JSON.parse(raw);
		if (!Array.isArray(parsed)) {
			return [];
		}
		return parsed.filter((item) => typeof item === "string");
	} catch {
		return [];
	}
}

export function writeStringArray(key, values) {
	localStorage.setItem(key, JSON.stringify(values));
}

export function readBooleanSetting(key, fallback) {
	const raw = localStorage.getItem(key);
	if (raw === null) {
		return fallback;
	}
	return raw !== "false";
}

export function readNumberSetting(key, fallback, min, max) {
	const raw = localStorage.getItem(key);
	if (raw === null) {
		return fallback;
	}
	const n = Number.parseFloat(raw);
	if (!Number.isFinite(n)) {
		return fallback;
	}
	return Math.max(min, Math.min(max, n));
}
