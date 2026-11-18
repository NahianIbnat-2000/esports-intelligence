"use client";

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { apiGet, type Envelope } from "@/lib/api";

type Params = Record<string, string | number | boolean | null | undefined>;

/** GET an API path with react-query caching. Pass enabled=false to wait. */
export function useApi<T>(path: string | null, params?: Params, enabled = true) {
  return useQuery<Envelope<T>, Error>({
    queryKey: [path, params],
    queryFn: () => apiGet<T>(path as string, params),
    enabled: enabled && path !== null,
    placeholderData: keepPreviousData,
  });
}
