import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = { title: "Global Index" };

export default function Page() {
  return <View />;
}
