import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = { title: "Documentation" };

export default function Page() {
  return <View />;
}
