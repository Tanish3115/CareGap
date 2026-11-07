"use client";

import { useCallback, useEffect, useRef } from "react";

/** Move to requested content after React commits it, including async history responses. */
export function useDetailNavigation(targets: Record<string, unknown>) {
  const root = useRef<HTMLElement | null>(null);
  const previous = useRef(targets);
  useEffect(() => {
    const changed = Object.keys(targets).filter(
      (key) => targets[key] && !Object.is(targets[key], previous.current[key]),
    );
    previous.current = targets;
    if (!root.current || root.current.closest("[hidden]")) return;
    // The last destination takes priority when an action opens a parent and its child together.
    const key = changed.at(-1);
    if (!key) return;
    const target = root.current.querySelector<HTMLElement>(`[data-detail-target="${key}"]`);
    if (!target) return;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent instanceof HTMLDetailsElement) parent.open = true;
    }
    target.tabIndex = -1;
    target.style.scrollMarginTop = "7rem";
    target.focus({ preventScroll: true });
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
      block: "start",
    });
  });
  return useCallback((element: HTMLElement | null) => {
    root.current = element;
  }, []);
}
