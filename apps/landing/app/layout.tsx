import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-inter-mono",
  display: "swap",
});

const siteUrl = "https://pmfinops.dev";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "PM+FinOps — Cada hora trabajada es un evento financiero",
    template: "%s · PM+FinOps",
  },
  description:
    "PM+FinOps unifica project management y operaciones financieras sobre ledgers inmutables. Margen, SLA y costos derivados automáticamente desde el trabajo real.",
  keywords: [
    "FinOps",
    "Project Management",
    "SaaS",
    "Multi-tenant",
    "Ledger inmutable",
    "Costos",
    "SLA",
  ],
  authors: [{ name: "PM+FinOps" }],
  openGraph: {
    type: "website",
    locale: "es_CL",
    url: siteUrl,
    siteName: "PM+FinOps",
    title: "PM+FinOps — Cada hora trabajada es un evento financiero",
    description:
      "Convergencia de PM y FinOps sobre ledgers inmutables. Margen y SLA derivados del trabajo real.",
  },
  twitter: {
    card: "summary_large_image",
    title: "PM+FinOps — Cada hora trabajada es un evento financiero",
    description:
      "Convergencia de PM y FinOps sobre ledgers inmutables.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#0a0e14",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
