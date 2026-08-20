import type { Metadata } from "next";
import "./globals.css";
import SiteChrome from "@/components/SiteChrome";

export const metadata: Metadata = {
  title: "Fintech Onchain",
  description:
    "Real-time fintech and crypto news, scored and curated automatically.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <SiteChrome />
        {children}
      </body>
    </html>
  );
}
