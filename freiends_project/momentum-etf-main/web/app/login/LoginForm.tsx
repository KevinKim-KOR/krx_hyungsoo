"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

function buildGoogleLoginHref(nextPath: string): string {
  const params = new URLSearchParams({ next: nextPath });
  return `/api/auth/google/start?${params.toString()}`;
}

export function LoginForm() {
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";
  const error = searchParams.get("error");

  return (
    <div className="container container-tight py-4">
      <div className="text-center mb-4">
        <span className="loginBrandMark">Jason 투자</span>
      </div>
      <div className="card card-md">
        <div className="card-body">
          {error ? <div className="alert alert-danger mb-3">{error}</div> : null}

          <Link className="btn btn-primary w-100" href={buildGoogleLoginHref(nextPath)}>
            Google로 로그인
          </Link>
        </div>
      </div>
    </div>
  );
}
