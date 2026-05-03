import { readLegal } from "@/lib/legal";

export const metadata = { title: "Security — lunning" };
export const dynamic = "force-static";

export default async function SecurityPage() {
  const md = await readLegal("SECURITY.md");
  return (
    <article>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{md}</pre>
    </article>
  );
}
