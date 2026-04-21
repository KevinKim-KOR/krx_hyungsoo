import { NextRequest, NextResponse } from "next/server";

import {
  buildGoogleAuthUrl,
  createOAuthStateToken,
  getOAuthStateCookieName,
  getOAuthStateMaxAgeSeconds,
  resolveExternalOrigin,
} from "@/lib/auth";

export async function GET(request: NextRequest) {
  try {
    const origin = resolveExternalOrigin(
      request.nextUrl.origin,
      request.headers.get("x-forwarded-proto"),
      request.headers.get("x-forwarded-host"),
    );
    const nextPath = request.nextUrl.searchParams.get("next") || "/";
    const stateToken = await createOAuthStateToken(nextPath);
    const redirectUrl = buildGoogleAuthUrl(origin, stateToken);

    const response = NextResponse.redirect(redirectUrl);
    response.cookies.set({
      name: getOAuthStateCookieName(),
      value: stateToken,
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: getOAuthStateMaxAgeSeconds(),
    });
    return response;
  } catch (error) {
    const origin = resolveExternalOrigin(
      request.nextUrl.origin,
      request.headers.get("x-forwarded-proto"),
      request.headers.get("x-forwarded-host"),
    );
    const loginUrl = new URL("/login", origin);
    loginUrl.searchParams.set("error", error instanceof Error ? error.message : "Google 로그인을 시작할 수 없습니다.");
    return NextResponse.redirect(loginUrl);
  }
}
