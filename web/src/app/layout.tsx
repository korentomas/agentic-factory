import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "LailaTov — Autonomous Code Factory",
    template: "%s | LailaTov",
  },
  description:
    "A codebase that never sleeps. Connect your repo, assign issues, wake up to reviewed PRs.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://lailatov.dev"
  ),
  openGraph: {
    title: "LailaTov",
    description: "Autonomous code factory that never sleeps.",
    siteName: "LailaTov",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "LailaTov — Autonomous Code Factory",
    description: "A codebase that never sleeps.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
