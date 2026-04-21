import { NextRequest, NextResponse } from "next/server";

import {
  createSessionToken,
  exchangeGoogleCode,
  fetchGoogleUserInfo,
  getAuthCookieName,
  getOAuthStateCookieName,
  getSessionMaxAgeSeconds,
  isAllowedEmail,
  resolveExternalOrigin,
  verifyOAuthStateToken,
} from "@/lib/auth";

function buildLoginRedirect(origin: string, request: NextRequest, message: string): NextResponse {
  const loginUrl = new URL("/login", origin);
  loginUrl.searchParams.set("error", message);
  const nextPath = request.nextUrl.searchParams.get("next");
  if (nextPath) {
    loginUrl.searchParams.set("next", nextPath);
  }
  return NextResponse.redirect(loginUrl);
}

export async function GET(request: NextRequest) {
  try {
    const origin = resolveExternalOrigin(
      request.nextUrl.origin,
      request.headers.get("x-forwarded-proto"),
      request.headers.get("x-forwarded-host"),
    );
    const error = request.nextUrl.searchParams.get("error");
    if (error) {
      return buildLoginRedirect(origin, request, "Google 로그인이 취소되었거나 실패했습니다.");
    }

    const code = request.nextUrl.searchParams.get("code");
    const state = request.nextUrl.searchParams.get("state");
    const stateCookie = request.cookies.get(getOAuthStateCookieName())?.value;

    if (!code || !state || !stateCookie || state !== stateCookie) {
      return buildLoginRedirect(origin, request, "Google 로그인 상태 검증에 실패했습니다.");
    }

    const verifiedState = await verifyOAuthStateToken(stateCookie);
    if (!verifiedState) {
      return buildLoginRedirect(origin, request, "Google 로그인 상태가 만료되었습니다.");
    }

    const accessToken = await exchangeGoogleCode(origin, code);
    const user = await fetchGoogleUserInfo(accessToken);
    const email = String(user.email ?? "").trim().toLowerCase();
    const displayName = String(user.name ?? email).trim();

    if (!email || user.email_verified !== true) {
      return buildLoginRedirect(origin, request, "검증된 Google 이메일이 필요합니다.");
    }

    if (!isAllowedEmail(email)) {
      return buildLoginRedirect(origin, request, "허용되지 않은 계정입니다.");
    }

    const token = await createSessionToken(email, displayName);
    const response = NextResponse.redirect(new URL(verifiedState.next_path, origin));
    response.cookies.set({
      name: getAuthCookieName(),
      value: token,
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: getSessionMaxAgeSeconds(),
    });
    response.cookies.set({
      name: getOAuthStateCookieName(),
      value: "",
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 0,
    });
    return response;
  } catch (error) {
    const origin = resolveExternalOrigin(
      request.nextUrl.origin,
      request.headers.get("x-forwarded-proto"),
      request.headers.get("x-forwarded-host"),
    );
    return buildLoginRedirect(
      origin,
      request,
      error instanceof Error ? error.message : "Google 로그인 처리에 실패했습니다.",
    );
  }
}
