const encoder = new TextEncoder();
const decoder = new TextDecoder();

const AUTH_COOKIE_NAME = "momentum_etf_node_session";
const OAUTH_STATE_COOKIE_NAME = "momentum_etf_node_oauth_state";
const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;
const OAUTH_STATE_MAX_AGE_SECONDS = 60 * 10;

type SessionPayload = {
  email: string;
  display_name: string;
  exp: number;
};

type OAuthStatePayload = {
  nonce: string;
  next_path: string;
  exp: number;
};

type GoogleUserInfo = {
  email?: string;
  email_verified?: boolean;
  name?: string;
};

function getRequiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} 환경변수가 필요합니다.`);
  }
  return value;
}

function normalizeOrigin(value: string): string {
  return value.trim().replace(/\/+$/g, "");
}

function normalizePath(value: string | null | undefined): string {
  const raw = String(value ?? "").trim();
  if (!raw.startsWith("/") || raw.startsWith("//")) {
    return "/";
  }
  return raw;
}

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/g, "");
}

function fromBase64Url(value: string): Uint8Array {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  const binary = atob(normalized + padding);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

async function signValue(value: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(getRequiredEnv("AUTH_SESSION_SECRET")),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return toBase64Url(new Uint8Array(signature));
}

async function encodeSignedPayload(payload: object): Promise<string> {
  const encodedPayload = toBase64Url(encoder.encode(JSON.stringify(payload)));
  const signature = await signValue(encodedPayload);
  return `${encodedPayload}.${signature}`;
}

async function decodeSignedPayload<T>(token: string | undefined | null): Promise<T | null> {
  const raw = String(token ?? "").trim();
  if (!raw.includes(".")) {
    return null;
  }

  const [encodedPayload, signature] = raw.split(".", 2);
  if (!encodedPayload || !signature) {
    return null;
  }

  const expectedSignature = await signValue(encodedPayload);
  if (signature !== expectedSignature) {
    return null;
  }

  try {
    return JSON.parse(decoder.decode(fromBase64Url(encodedPayload))) as T;
  } catch {
    return null;
  }
}

export function getAuthCookieName(): string {
  return AUTH_COOKIE_NAME;
}

export function getOAuthStateCookieName(): string {
  return OAUTH_STATE_COOKIE_NAME;
}

export function getSessionMaxAgeSeconds(): number {
  return SESSION_MAX_AGE_SECONDS;
}

export function getOAuthStateMaxAgeSeconds(): number {
  return OAUTH_STATE_MAX_AGE_SECONDS;
}

export function getAllowedEmails(): Set<string> {
  const raw = getRequiredEnv("AUTH_ALLOWED_EMAILS");
  const emails = raw
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  if (emails.length === 0) {
    throw new Error("AUTH_ALLOWED_EMAILS 값이 비어 있습니다.");
  }
  return new Set(emails);
}

export function isAllowedEmail(email: string): boolean {
  return getAllowedEmails().has(email.trim().toLowerCase());
}

export function getGoogleClientId(): string {
  return getRequiredEnv("GOOGLE_CLIENT_ID");
}

export function getGoogleClientSecret(): string {
  return getRequiredEnv("GOOGLE_CLIENT_SECRET");
}

export function getAppBaseUrl(): string {
  const configured = process.env.APP_BASE_URL?.trim();
  if (configured) {
    return normalizeOrigin(configured);
  }

  if (process.env.NODE_ENV === "production") {
    throw new Error("APP_BASE_URL 환경변수가 필요합니다.");
  }

  return "http://localhost:3000";
}

export function resolveExternalOrigin(
  fallbackOrigin: string,
  forwardedProto?: string | null,
  forwardedHost?: string | null,
): string {
  const configured = process.env.APP_BASE_URL?.trim();
  if (configured) {
    return normalizeOrigin(configured);
  }

  const proto = String(forwardedProto ?? "").split(",")[0]?.trim();
  const host = String(forwardedHost ?? "").split(",")[0]?.trim();
  if (proto && host) {
    return normalizeOrigin(`${proto}://${host}`);
  }

  return normalizeOrigin(fallbackOrigin);
}

export function getGoogleCallbackUrl(origin: string): string {
  return `${normalizeOrigin(origin)}/api/auth/callback/google`;
}

export async function createSessionToken(email: string, displayName: string): Promise<string> {
  return encodeSignedPayload({
    email: email.trim().toLowerCase(),
    display_name: displayName.trim() || email.trim().toLowerCase(),
    exp: Date.now() + SESSION_MAX_AGE_SECONDS * 1000,
  } satisfies SessionPayload);
}

export async function verifySessionToken(token: string | undefined | null): Promise<SessionPayload | null> {
  const payload = await decodeSignedPayload<SessionPayload>(token);
  if (!payload?.email || !payload?.display_name || !payload?.exp) {
    return null;
  }
  if (payload.exp < Date.now()) {
    return null;
  }
  return payload;
}

export async function createOAuthStateToken(nextPath: string): Promise<string> {
  return encodeSignedPayload({
    nonce: crypto.randomUUID(),
    next_path: normalizePath(nextPath),
    exp: Date.now() + OAUTH_STATE_MAX_AGE_SECONDS * 1000,
  } satisfies OAuthStatePayload);
}

export async function verifyOAuthStateToken(token: string | undefined | null): Promise<OAuthStatePayload | null> {
  const payload = await decodeSignedPayload<OAuthStatePayload>(token);
  if (!payload?.nonce || !payload?.next_path || !payload?.exp) {
    return null;
  }
  if (payload.exp < Date.now()) {
    return null;
  }
  return {
    ...payload,
    next_path: normalizePath(payload.next_path),
  };
}

export function buildGoogleAuthUrl(origin: string, stateToken: string): string {
  const params = new URLSearchParams({
    client_id: getGoogleClientId(),
    redirect_uri: getGoogleCallbackUrl(origin),
    response_type: "code",
    scope: "openid email profile",
    state: stateToken,
    access_type: "online",
    prompt: "select_account",
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

export async function exchangeGoogleCode(origin: string, code: string): Promise<string> {
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: getGoogleClientId(),
      client_secret: getGoogleClientSecret(),
      redirect_uri: getGoogleCallbackUrl(origin),
      grant_type: "authorization_code",
    }),
    cache: "no-store",
  });

  const payload = (await response.json()) as { access_token?: string; error?: string; error_description?: string };
  if (!response.ok || !payload.access_token) {
    throw new Error(payload.error_description || payload.error || "Google 토큰 교환에 실패했습니다.");
  }
  return payload.access_token;
}

export async function fetchGoogleUserInfo(accessToken: string): Promise<GoogleUserInfo> {
  const response = await fetch("https://openidconnect.googleapis.com/v1/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  const payload = (await response.json()) as GoogleUserInfo & { error?: string; error_description?: string };
  if (!response.ok) {
    throw new Error(payload.error_description || payload.error || "Google 사용자 정보를 가져오지 못했습니다.");
  }
  return payload;
}
