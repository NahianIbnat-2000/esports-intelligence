import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = { title: "Data Explorer" };

export default function Page() {
  return <View />;
}
