// Utility functions for text processing, parsing, and normalization

export function toInt(value, fallback) {
	const parsed = Number.parseInt(String(value), 10);
	if (Number.isNaN(parsed)) {
		return fallback;
	}
	return parsed;
}

export function formatNumber(value) {
	return new Intl.NumberFormat().format(value);
}

export function normalizeDanbooruCategory(value) {
	const category = toInt(value, -1);
	if (category < 0) {
		return null;
	}
	return category;
}

export function getDanbooruCategoryLabel(value) {
	switch (normalizeDanbooruCategory(value)) {
		case 0:
			return "general";
		case 1:
			return "artist";
		case 2:
			return "unknown";
		case 3:
			return "copyright";
		case 4:
			return "character";
		case 5:
			return "meta";
		default:
			return null;
	}
}

export function parseJsonStorage(key, fallback) {
	try {
		const raw = localStorage.getItem(key);
		if (!raw) {
			return fallback;
		}
		return JSON.parse(raw);
	} catch (error) {
		return fallback;
	}
}

export function normalizeSearchText(value) {
	return String(value || "")
		.toLowerCase()
		.replace(/[\\/_:\-]+/g, " ")
		.replace(/[^a-z0-9\s]+/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

export function normalizeAliases(value) {
	if (!value) {
		return [];
	}
	const raw = Array.isArray(value) ? value : String(value).split(/[|,]/g);
	const deduped = new Set();
	for (const item of raw) {
		let alias = String(item || "").trim();
		if (alias.startsWith('"') && alias.endsWith('"') && alias.length >= 2) {
			alias = alias.slice(1, -1);
		}
		if (alias.startsWith("'") && alias.endsWith("'") && alias.length >= 2) {
			alias = alias.slice(1, -1);
		}
		if (!alias) {
			continue;
		}
		deduped.add(alias.toLowerCase());
	}
	return [...deduped.values()];
}

export function parseCsvRow(line) {
	const text = String(line || "");
	if (!text) {
		return [];
	}

	const parts = [];
	let current = "";
	let inQuotes = false;

	for (let i = 0; i < text.length; i += 1) {
		const ch = text[i];
		if (ch === '"') {
			if (inQuotes && text[i + 1] === '"') {
				current += '"';
				i += 1;
				continue;
			}
			inQuotes = !inQuotes;
			continue;
		}
		if (ch === "," && !inQuotes) {
			parts.push(current.trim());
			current = "";
			continue;
		}
		current += ch;
	}

	parts.push(current.trim());
	return parts;
}

export function toCsvField(value) {
	const text = String(value ?? "");
	if (!text.includes(",") && !text.includes('"') && !text.includes("\n") && !text.includes("\r")) {
		return text;
	}
	return `"${text.replace(/"/g, '""')}"`;
}

export function mergeAliases(left, right) {
	const merged = new Set([...(left || []), ...(right || [])]);
	return [...merged.values()];
}

export function parseCustomWordEntry(rawText) {
	const text = String(rawText || "").trim();
	if (!text) {
		return null;
	}

	if (text.includes("=>")) {
		const [canonicalRaw, aliasesRaw] = text.split("=>", 2);
		const canonical = String(canonicalRaw || "").trim();
		if (!canonical) {
			return null;
		}
		return {
			text: canonical,
			aliases: normalizeAliases(aliasesRaw),
		};
	}

	if (text.includes("|")) {
		const parts = text
			.split("|")
			.map((part) => part.trim())
			.filter(Boolean);
		if (!parts.length) {
			return null;
		}
		return {
			text: parts[0],
			aliases: normalizeAliases(parts.slice(1)),
		};
	}

	return {
		text,
		aliases: [],
	};
}

export function getSearchQueryVariations(query) {
	const trimmed = String(query || "").trim().toLowerCase();
	if (!trimmed) {
		return [];
	}

	const variants = new Set([trimmed, normalizeSearchText(trimmed)]);

	if (trimmed.includes(" ")) {
		variants.add(trimmed.replace(/\s+/g, "_"));
		variants.add(trimmed.replace(/\s+/g, ""));
	}

	if (trimmed.includes("_")) {
		variants.add(trimmed.replace(/_+/g, " "));
		variants.add(trimmed.replace(/_+/g, ""));
	}

	const spaceParts = trimmed.split(/\s+/g).filter(Boolean);
	if (spaceParts.length > 1) {
		variants.add(spaceParts[spaceParts.length - 1]);
	}

	for (const value of [...variants]) {
		const normalized = normalizeSearchText(value);
		variants.add(normalized);
		variants.add(normalized.replace(/\s+/g, "_"));
		variants.add(normalized.replace(/\s+/g, ""));
	}

	return [...variants.values()].filter(Boolean).slice(0, 12);
}

export function normalizeEntry(entry, source) {
	if (!entry) {
		return null;
	}

	if (typeof entry === "string") {
		const parsed = parseCustomWordEntry(entry);
		const text = String(parsed?.text || "").trim();
		if (!text) {
			return null;
		}
		return {
			text,
			source,
			count: null,
			aliases: normalizeAliases(parsed?.aliases),
		};
	}

	if (typeof entry !== "object") {
		return null;
	}

	const text = String(entry.text || entry.name || "").trim();
	if (!text) {
		return null;
	}

	const count = typeof entry.count === "number" ? entry.count : typeof entry.post_count === "number" ? entry.post_count : null;
	const category = normalizeDanbooruCategory(entry.category ?? entry.tag_category);
	const aliases = normalizeAliases(entry.aliases ?? entry.alias);
	return {
		text,
		source,
		count: Number.isFinite(count) ? count : null,
		category,
		aliases,
	};
}

export function dedupeEntries(entries) {
	const map = new Map();
	for (const entry of entries) {
		if (!entry?.text) {
			continue;
		}
		const key = entry.text.toLowerCase();
		const prev = map.get(key);
		if (!prev) {
			map.set(key, entry);
			continue;
		}
		const prevCount = typeof prev.count === "number" ? prev.count : -1;
		const nextCount = typeof entry.count === "number" ? entry.count : -1;
		if (nextCount > prevCount) {
			map.set(key, {
				...entry,
				aliases: mergeAliases(prev.aliases, entry.aliases),
			});
			continue;
		}
		map.set(key, {
			...prev,
			aliases: mergeAliases(prev.aliases, entry.aliases),
		});
	}
	return [...map.values()];
}

export function parseCustomWords(text) {
	if (!text) {
		return [];
	}
	return dedupeEntries(
		text
			.split(/[\n,]/g)
			.map((v) => normalizeEntry(v, "custom"))
			.filter(Boolean),
	);
}


export function hasLikelySwappedCountCategory(entries) {
	if (!Array.isArray(entries) || !entries.length) {
		return false;
	}

	const sampleSize = Math.min(entries.length, 500);
	let checked = 0;
	let suspicious = 0;

	for (let i = 0; i < sampleSize; i += 1) {
		const entry = entries[i];
		if (typeof entry?.count !== "number" || typeof entry?.category !== "number") {
			continue;
		}
		checked += 1;
		if (entry.count <= 20 && entry.category > 1000) {
			suspicious += 1;
		}
	}

	if (checked < 25) {
		return false;
	}

	return suspicious / checked >= 0.3;
}
