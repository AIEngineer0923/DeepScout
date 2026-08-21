import { Suspense } from "react";
import { LoginPageClient } from "./LoginPageClient";

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="muted">…</p>}>
      <LoginPageClient />
    </Suspense>
  );
}
