import type { Metadata } from "next";
import { Karla, Fraunces } from "next/font/google";
import "./globals.css";

const karla = Karla({
  variable: "--font-karla",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT", "WONK"],
});

import { ToastProvider } from "@/components/ui/ToastContext";

import { Shell } from "@/components/layout/Shell";

export const metadata: Metadata = {
  title: "PInSight Dashboard",
  description: "Agentic Payment Incident Investigation Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${karla.variable} ${fraunces.variable}`}>
        <ToastProvider>
          <Shell>
            {children}
          </Shell>
        </ToastProvider>
      </body>
    </html>
  );
}
