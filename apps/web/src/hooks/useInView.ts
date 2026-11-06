import { useEffect, useRef, useState } from "react";
export function useInView<T extends Element>(margin = "0px", once = false) {
  const ref = useRef<T>(null);
  const [inView, set] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver(([e]) => { set(e.isIntersecting); if (once && e.isIntersecting) io.disconnect(); }, { rootMargin: margin });
    io.observe(el); return () => io.disconnect();
  }, [margin, once]);
  return [ref, inView] as const;
}
export const prefersReduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
