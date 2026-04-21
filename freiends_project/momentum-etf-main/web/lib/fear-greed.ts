export type FearGreedSummary = {
  score: number | null;
  label: string | null;
  previous_close_score: number | null;
  updated_at: string | null;
};

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
}

function toStringValue(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }

  return null;
}

function toIsoTimestamp(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    const timestamp = value > 10_000_000_000 ? value : value * 1000;
    return new Date(timestamp).toISOString();
  }

  if (typeof value === "string" && value.trim()) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      const timestamp = numeric > 10_000_000_000 ? numeric : numeric * 1000;
      return new Date(timestamp).toISOString();
    }

    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString();
    }
  }

  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function extractPreviousCloseScore(value: unknown): number | null {
  if (!isRecord(value)) {
    return null;
  }

  const directPreviousClose = toNumber(value.previous_close);
  if (directPreviousClose !== null) {
    return directPreviousClose;
  }

  if (isRecord(value.previous_close)) {
    const previousClose = toNumber(
      value.previous_close.score ??
        value.previous_close.value ??
        value.previous_close.index_value ??
        value.previous_close.current_score,
    );
    if (previousClose !== null) {
      return previousClose;
    }
  }

  return toNumber(value.previous_close_score ?? value.previousCloseScore);
}

function findPreviousCloseScore(value: unknown, depth = 0): number | null {
  if (depth > 8) {
    return null;
  }

  const direct = extractPreviousCloseScore(value);
  if (direct !== null) {
    return direct;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findPreviousCloseScore(item, depth + 1);
      if (found !== null) {
        return found;
      }
    }
    return null;
  }

  if (!isRecord(value)) {
    return null;
  }

  for (const nested of Object.values(value)) {
    const found = findPreviousCloseScore(nested, depth + 1);
    if (found !== null) {
      return found;
    }
  }

  return null;
}

function findSummaryNode(value: unknown, depth = 0): FearGreedSummary | null {
  if (depth > 8) {
    return null;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findSummaryNode(item, depth + 1);
      if (found) {
        return found;
      }
    }
    return null;
  }

  if (!isRecord(value)) {
    return null;
  }

  const score = toNumber(
    value.score ?? value.value ?? value.index_value ?? value.current_score ?? value.currentValue,
  );
  const label = toStringValue(value.rating ?? value.label ?? value.status ?? value.text);
  const updatedAt = toIsoTimestamp(
    value.timestamp ?? value.updated_at ?? value.updatedAt ?? value.last_updated ?? value.lastUpdated,
  );
  const previousClose = extractPreviousCloseScore(value);

  if (score !== null && label) {
    return {
      score,
      label,
      previous_close_score: previousClose,
      updated_at: updatedAt,
    };
  }

  for (const nested of Object.values(value)) {
    const found = findSummaryNode(nested, depth + 1);
    if (found) {
      return found;
    }
  }

  return null;
}

export function parseFearGreedSummary(payload: unknown): FearGreedSummary {
  const summary = findSummaryNode(payload) ?? {
    score: null,
    label: null,
    previous_close_score: null,
    updated_at: null,
  };

  return {
    ...summary,
    previous_close_score: summary.previous_close_score ?? findPreviousCloseScore(payload),
  };
}
