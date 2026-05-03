import { readLegal } from "@/lib/legal";

export const metadata = { title: "Privacy — lunning" };
export const dynamic = "force-static";

export default async function PrivacyPage() {
  const md = await readLegal("PRIVACY.md");
  return (
    <article>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{md}</pre>
    </article>
  );
}
