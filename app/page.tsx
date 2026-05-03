import { redirect } from "next/navigation";
import { createGame } from "@/lib/actions";

export default function Home() {
  async function action(formData: FormData) {
    "use server";
    const title = String(formData.get("title") ?? "").trim();
    const sidesRaw = String(formData.get("sides") ?? "").trim();
    const sides = sidesRaw
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!title || sides.length < 2) {
      throw new Error("Title and at least two sides are required.");
    }
    const id = await createGame({ title, sides });
    redirect(`/games/${id}`);
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">Start a new game</h1>
      <p className="mt-2 text-neutral-600">
        Anyone with the game URL can score. Every change is logged forever.
      </p>
      <form action={action} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium">Game title</span>
          <input
            name="title"
            required
            placeholder="Tuesday tennis singles"
            className="mt-1 block w-full rounded border border-neutral-300 bg-white px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Sides (one per line, or comma-separated)</span>
          <textarea
            name="sides"
            required
            rows={3}
            placeholder={"Alice\nBob"}
            className="mt-1 block w-full rounded border border-neutral-300 bg-white px-3 py-2 font-mono"
          />
        </label>
        <button
          type="submit"
          className="rounded bg-neutral-900 px-4 py-2 text-white hover:bg-neutral-700"
        >
          Create game
        </button>
      </form>
    </div>
  );
}
