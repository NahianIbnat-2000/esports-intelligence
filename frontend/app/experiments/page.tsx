import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = {
  title: "Experiments",
  description: "Walk-forward evaluation over five test years: Elo, league levels, form, roster and player-level ratings, with series-clustered uncertainty intervals.",
};

export default function Page() {
  return <View />;
}
