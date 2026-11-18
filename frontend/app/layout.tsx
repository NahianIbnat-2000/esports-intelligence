import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: { default: "Esports Intelligence", template: "%s | Esports Intelligence" },
  description: "Beyond the Game. Inside the Data. Research-driven esports analytics built on historical professional League of Legends data.",
};

export const viewport: Viewport = { themeColor: "#080D18", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
