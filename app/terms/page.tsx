import { readLegal } from "@/lib/legal";

export const metadata = { title: "Terms — lunning" };
export const dynamic = "force-static";

export default async function TermsPage() {
  const md = await readLegal("TERMS.md");
  return (
    <article>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{md}</pre>
    </article>
  );
}
