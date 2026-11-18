"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type GameSlug = "lol" | "valorant" | "cs2";
export const GAMES: { slug: GameSlug; name: string; short: string }[] = [
  { slug: "lol", name: "League of Legends", short: "LoL" },
  { slug: "valorant", name: "VALORANT", short: "VAL" },
  { slug: "cs2", name: "Counter-Strike 2", short: "CS2" },
];

/** Games shown in the interface. VALORANT and CS2 stay hidden until they have verified data;
 * set NEXT_PUBLIC_VISIBLE_GAMES=lol,valorant,cs2 to show them again. */
const visible = (process.env.NEXT_PUBLIC_VISIBLE_GAMES || "lol").split(",").map((x) => x.trim());
export const VISIBLE_GAMES = GAMES.filter((g) => visible.includes(g.slug));

const GameContext = createContext<{ game: GameSlug; setGame: (g: GameSlug) => void }>({
  game: "lol",
  setGame: () => {},
});

export function useGame() {
  return useContext(GameContext);
}

const STORAGE_KEY = "ei.game";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 5 * 60_000, retry: 1, refetchOnWindowFocus: false } },
      }),
  );
  const [game, setGameState] = useState<GameSlug>("lol");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (VISIBLE_GAMES.some((g) => g.slug === saved)) setGameState(saved as GameSlug);
    } catch {
      /* storage unavailable: keep default */
    }
  }, []);

  const setGame = (g: GameSlug) => {
    setGameState(g);
    try {
      window.localStorage.setItem(STORAGE_KEY, g);
    } catch {
      /* ignore */
    }
  };

  return (
    <QueryClientProvider client={client}>
      <GameContext.Provider value={{ game, setGame }}>{children}</GameContext.Provider>
    </QueryClientProvider>
  );
}
