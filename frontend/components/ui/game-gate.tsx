"use client";

import { GAMES, useGame } from "@/components/providers";
import { IntegrationPending, Segmented } from "@/components/ui/primitives";
import type { ReactNode } from "react";

export function GameSwitch() {
  const { game, setGame } = useGame();
  return (
    <Segmented label="Game" value={game} onChange={setGame}
      options={GAMES.map((g) => ({ value: g.slug, label: g.short }))} />
  );
}

/** Shows children only for League of Legends; other games get an explicit
 * integration-pending state instead of empty-looking widgets. */
export function LolOnly({ children }: { children: ReactNode }) {
  const { game } = useGame();
  if (game !== "lol") return <IntegrationPending game={GAMES.find((g) => g.slug === game)?.name || game} />;
  return <>{children}</>;
}
