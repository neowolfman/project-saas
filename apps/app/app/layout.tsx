import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Dashboard — SaaS PM+FinOps",
  description:
    "Plataforma SaaS de gestión de proyectos y FinOps. Métricas de margen, horas y SLA en tiempo real.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={inter.variable}>
      <body className="bg-base text-fg-primary font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
