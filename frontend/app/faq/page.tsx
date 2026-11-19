import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = {
  title: "FAQ and glossary",
  description: "Plain-language answers and definitions: Elo ratings, Brier score, series, sides, roles and the economics measures used on Esports Intelligence.",
};

export default function Page() {
  return <View />;
}
