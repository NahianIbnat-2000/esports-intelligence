"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type GameSlug = "lol" | "valorant" | "cs2";
export const GAMES: { slug: GameSlug; name: string; short: string }[] = [
  { slug: "lol", name: "League of Legends", short: "LoL" },
  { slug: "valorant", name: "VALORANT", short: "VAL" },
  { slug: "cs2", name: "Counter-Strike 2", short: "CS2" },
];

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
      if (saved === "lol" || saved === "valorant" || saved === "cs2") setGameState(saved);
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
