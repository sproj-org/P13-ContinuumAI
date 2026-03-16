"use client";

import Link from "next/link";
import Noise from "@/components/ui/Noise";
import ElectricBorder from "@/components/ui/ElectricBorder";
import { Mail, Phone, MapPin, HelpCircle, Database, ArrowLeft, MessageSquare, Headphones } from "lucide-react";

export default function SupportPage() {
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
                  <Headphones className="w-8 h-8 text-white" />
                </div>
              </div>
              <h1 className="text-3xl font-bold text-slate-900 mb-2">
                Support &amp; Services
              </h1>
              <p className="text-slate-600 max-w-md mx-auto">
                Need help with ContinuumAI or want to connect a new database? 
                Our team is here to assist you every step of the way.
              </p>
            </div>

            {/* Support Options */}
            <div className="space-y-6">
              {/* Technical Support */}
              <div className="bg-gradient-to-r from-indigo-50 to-violet-50 rounded-xl p-6 border border-indigo-100">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                    <HelpCircle className="w-5 h-5 text-[#4f46e5]" />
                  </div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    Technical Support
                  </h2>
                </div>
                <p className="text-slate-600 text-sm mb-4">
                  Having issues with the platform? Our technical team is available to help resolve any problems.
                </p>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="w-4 h-4 text-[#4f46e5]" />
                    <a href="mailto:support@continuumai.com" className="text-[#4f46e5] hover:text-indigo-700 font-medium text-sm">
                      support@continuumai.com
                    </a>
                  </div>
                  <div className="flex items-center gap-3">
                    <MessageSquare className="w-4 h-4 text-[#4f46e5]" />
                    <span className="text-slate-600 text-sm">Response within 24 hours</span>
                  </div>
                </div>
              </div>

              {/* Connect New Database */}
              <div className="bg-gradient-to-r from-slate-50 to-indigo-50/50 rounded-xl p-6 border border-slate-200">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
                    <Database className="w-5 h-5 text-slate-600" />
                  </div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    Connect a New Database
                  </h2>
                </div>
                <p className="text-slate-600 text-sm mb-4">
                  Want to connect your own PostgreSQL, MySQL, or other data sources to ContinuumAI? 
                  Contact our data engineering team to get started.
                </p>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="w-4 h-4 text-[#4f46e5]" />
                    <a href="mailto:data@continuumai.com" className="text-[#4f46e5] hover:text-indigo-700 font-medium text-sm">
                      data@continuumai.com
                    </a>
                  </div>
                  <div className="flex items-center gap-3">
                    <Phone className="w-4 h-4 text-[#4f46e5]" />
                    <a href="tel:+1-555-123-4567" className="text-[#4f46e5] hover:text-indigo-700 font-medium text-sm">
                      +1 (555) 123-4567
                    </a>
                  </div>
                </div>
              </div>

              {/* General Contact */}
              <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  General Inquiries
                </h2>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="w-4 h-4 text-slate-500" />
                    <a href="mailto:hello@continuumai.com" className="text-slate-700 hover:text-[#4f46e5] text-sm">
                      hello@continuumai.com
                    </a>
                  </div>
                  <div className="flex items-center gap-3">
                    <MapPin className="w-4 h-4 text-slate-500" />
                    <span className="text-slate-600 text-sm">
                      123 Analytics Way, Suite 456, San Francisco, CA 94105
                    </span>
                  </div>
                </div>
              </div>

              {/* Back Button */}
              <div className="text-center pt-2">
                <Link
                  href="/dashboard"
                  className="cursor-target inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-[#4f46e5] to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 transition-colors shadow-lg"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Dashboard
                </Link>
              </div>
            </div>
          </div>
        </ElectricBorder>
      </div>
    </div>
  );
}
