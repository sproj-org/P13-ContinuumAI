"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SignupPage() {
  const router = useRouter();

  // Redirect to get-access page
  // Public signup is no longer available
  useEffect(() => {
    router.replace("/get-access");
  }, [router]);

  return (
    <div className="h-screen w-screen overflow-hidden flex items-center justify-center bg-white">
      <div className="text-lg text-slate-900">Redirecting...</div>
    </div>
  );
}
