import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { QueryProvider } from "@/lib/query-provider";
import { ToastProvider } from "@/lib/toast-context";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ContinuumAi",
  description: "The Future of Business Intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Special+Gothic+Expanded+One&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className={`${inter.variable} antialiased font-sans`}
      >
        <QueryProvider>
          <AuthProvider>
            <ToastProvider>{children}</ToastProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
