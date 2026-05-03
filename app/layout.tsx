import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "lunning — open scorekeeping",
  description: "Auditable scorekeeping for amateur sports. Every change is logged.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="mx-auto max-w-2xl px-4 py-10">
          <a href="/" className="text-sm font-mono text-neutral-500 hover:text-neutral-900">
            lunning
          </a>
          <div className="mt-6">{children}</div>
        </main>
      </body>
    </html>
  );
}
