import type { Metadata } from "next";
import "./globals.css";
import "katex/dist/katex.min.css";
import { Providers } from "./providers";
import MixpanelInitializer from "./MixpanelInitializer";
import { Toaster } from "@/components/ui/sonner";
import TailwindBrowserRuntime from "@/components/runtime/TailwindBrowserRuntime";
export const metadata: Metadata = {
  title: "Slidoxa — AI presentation workspace",
  description:
    "Slidoxa is an AI presentation workspace with custom layouts, multi-model support and PDF/PPTX export. Derived from Presenton (Apache-2.0).",
  keywords: [
    "Slidoxa",
    "AI presentation generator",
    "data storytelling",
    "data visualization tool",
    "presentation generator",
    "interactive presentations",
    "professional slides",
  ],
  openGraph: {
    title: "Slidoxa — AI presentation workspace",
    description:
      "Slidoxa is an AI presentation workspace with custom layouts, multi-model support and PDF/PPTX export.",
    siteName: "Slidoxa",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Slidoxa — AI presentation workspace",
    description:
      "Slidoxa is an AI presentation workspace with custom layouts, multi-model support and PDF/PPTX export.",
  },
  manifest: "/site.webmanifest",
  icons: {
    icon: [
      { url: "/icon2.png", sizes: "192x192", type: "image/png" },
      { url: "/slidoxa-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
    shortcut: ["/favicon.ico"],
  },
  themeColor: "#0F1020",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  return (
    <html lang="en">
      <body className="antialiased">
        <Providers>
          <MixpanelInitializer>

            {children}

          </MixpanelInitializer>
        </Providers>
        <TailwindBrowserRuntime />
        <Toaster position="top-center" />
      </body>
    </html>
  );
}
