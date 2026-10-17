import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AEGIS — Autonomous Pre-Trade Risk & Self-Monitoring Service",
  description:
    "Off-chain autonomous trading risk gate and reusable pre-trade evaluation service. Uses official OKX Agent Trade Kit (ATK) market observations, LAYA operational risk classification, bounded EVREN reasoning, deterministic Python policy enforcement, and Avalanche Fuji (43113) ERC-8004 / receipt verification.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">
        {children}
      </body>
    </html>
  );
}
