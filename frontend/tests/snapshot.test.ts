import { describe, expect, it } from "vitest";
import { canonicalKey, fnv1a } from "@/lib/snapshot";

describe("snapshot keys", () => {
  it("drops empty values and sorts keys", () => {
    expect(canonicalKey("/teams", { sort: "elo", game: "lol", league: "", page: 1, q: undefined }))
      .toBe("/teams?game=lol&page=1&sort=elo");
    expect(canonicalKey("/games")).toBe("/games");
  });
  it("hashes like the Python exporter (FNV-1a 32)", () => {
    // values computed with backend.app.snapshot.fnv1a
    expect(fnv1a("")).toBe("811c9dc5");
    expect(fnv1a("/games")).toBe("24196225");
    expect(fnv1a("/overview?game=lol&league=LCK")).toBe("5d795a1a");
  });
});
