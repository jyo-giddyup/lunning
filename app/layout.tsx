import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "lunning — open scorekeeping",
  description: "Auditable scorekeeping for amateur sports. Every change is logged.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10">
          <a
            href="/"
            className="text-sm font-mono text-neutral-500 hover:text-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-400 focus:ring-offset-2"
          >
            lunning
          </a>
          <div className="mt-6">{children}</div>
        </main>
        <footer className="mx-auto w-full max-w-2xl px-4 py-6 text-xs text-neutral-500">
          <nav className="flex flex-wrap gap-x-4 gap-y-2">
            <a href="/privacy" className="hover:text-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-400">
              Privacy
            </a>
            <a href="/terms" className="hover:text-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-400">
              Terms
            </a>
            <a href="/security" className="hover:text-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-400">
              Security
            </a>
            <a
              href="https://github.com/jyo-giddyup/lunning"
              className="hover:text-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-400"
            >
              Source
            </a>
          </nav>
        </footer>
      </body>
    </html>
  );
}
