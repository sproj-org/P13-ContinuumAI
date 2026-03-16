"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useEffect } from "react";
import Noise from "@/components/ui/Noise";
import ElectricBorder from "@/components/ui/ElectricBorder";
import { Mail, Phone, MapPin, Building2, ArrowLeft } from "lucide-react";

export default function GetAccessPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="h-screen w-screen overflow-hidden flex items-center justify-center bg-white">
        <div className="text-lg text-slate-900">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-screen overflow-hidden flex items-center justify-center bg-white py-12">
      {/* Noise Background */}
      <div className="absolute inset-0 z-0 overflow-hidden">
        <Noise
          patternSize={250}
          patternScaleX={1}
          patternScaleY={1}
          patternRefreshInterval={2}
          patternAlpha={8}
        />
      </div>

      <div className="relative z-10 w-full max-w-2xl px-4">
        <ElectricBorder
          color="#4f46e5"
          speed={1}
          chaos={0.08}
          borderRadius={16}
        >
          <div className="bg-white/95 backdrop-blur-sm p-8 rounded-2xl shadow-2xl">
            {/* Header */}
            <div className="text-center mb-8">
              <div className="flex justify-center mb-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#4f46e5] to-indigo-600 flex items-center justify-center shadow-lg">
                  <Building2 className="w-8 h-8 text-white" />
                </div>
              </div>
              <h1 className="text-3xl font-bold text-slate-900 mb-2">
                Get Access to ContinuumAI
              </h1>
              <p className="text-slate-600 max-w-md mx-auto">
                ContinuumAI is an enterprise platform. Contact our team to onboard your organization 
                and get access to powerful business analytics.
              </p>
            </div>

            {/* Contact Information */}
            <div className="space-y-6">
              <div className="bg-gradient-to-r from-indigo-50 to-violet-50 rounded-xl p-6 border border-indigo-100">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  Contact Our Sales Team
                </h2>
                
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <Mail className="w-5 h-5 text-[#4f46e5]" />
                    </div>
                    <div>
                      <p className="text-sm text-slate-500">Email</p>
                      <a 
                        href="mailto:sales@continuumai.com" 
                        className="text-[#4f46e5] hover:text-indigo-700 font-medium"
                      >
                        sales@continuumai.com
                      </a>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <Phone className="w-5 h-5 text-[#4f46e5]" />
                    </div>
                    <div>
                      <p className="text-sm text-slate-500">Phone</p>
                      <a 
                        href="tel:+1-555-123-4567" 
                        className="text-[#4f46e5] hover:text-indigo-700 font-medium"
                      >
                        +1 (555) 123-4567
                      </a>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                      <MapPin className="w-5 h-5 text-[#4f46e5]" />
                    </div>
                    <div>
                      <p className="text-sm text-slate-500">Address</p>
                      <p className="text-slate-700">
                        123 Analytics Way, Suite 456<br />
                        San Francisco, CA 94105
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* What You Get */}
              <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  What&apos;s Included
                </h2>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <span className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="w-2 h-2 rounded-full bg-[#4f46e5]"></span>
                    </span>
                    <span className="text-slate-700">Full data onboarding and configuration</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="w-2 h-2 rounded-full bg-[#4f46e5]"></span>
                    </span>
                    <span className="text-slate-700">Custom user accounts for your team</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="w-2 h-2 rounded-full bg-[#4f46e5]"></span>
                    </span>
                    <span className="text-slate-700">AI-powered analytics with VizAgent assistant</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="w-2 h-2 rounded-full bg-[#4f46e5]"></span>
                    </span>
                    <span className="text-slate-700">Dedicated support and training</span>
                  </li>
                </ul>
              </div>

              {/* CTA */}
              <div className="text-center pt-2">
                <p className="text-slate-500 text-sm mb-4">
                  Already have an account?{" "}
                  <Link href="/login" className="text-[#4f46e5] hover:text-indigo-700 font-medium">
                    Login
                  </Link>
                </p>
                <Link
                  href="/"
                  className="cursor-target inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-[#4f46e5] to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 transition-colors shadow-lg"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Home
                </Link>
              </div>
            </div>
          </div>
        </ElectricBorder>
      </div>
    </div>
  );
}
