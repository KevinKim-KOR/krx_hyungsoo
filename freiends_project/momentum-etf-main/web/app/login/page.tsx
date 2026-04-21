import { Suspense } from "react";

import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  return (
    <main className="loginPage">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
