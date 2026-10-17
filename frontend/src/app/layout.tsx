import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AEGIS — AI-Powered Pre-Trade Risk Monitoring & Verification",
  description:
    "Off-chain autonomous trading risk gate and reusable pre-trade evaluation service. Uses official OKX Agent Trade Kit (ATK) market observations, LAYA operational risk classification, bounded EVREN reasoning, deterministic Python policy enforcement, and Avalanche Fuji (43113) ERC-8004 / receipt verification.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark h-full antialiased ${inter.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-full flex flex-col bg-[#0A0D10] text-[#E6EDF3] selection:bg-[#4EE1C2]/25 selection:text-[#4EE1C2]">
        {children}
      </body>
    </html>
  );
}

