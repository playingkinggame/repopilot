import { createContext, ReactNode, useCallback, useContext, useState } from "react";

type Kind = "error" | "success";
const Ctx = createContext<(msg: string, kind?: Kind) => void>(() => undefined);
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; kind: Kind }[]>([]);
  const push = useCallback((msg: string, kind: Kind = "success") => {
    const id = Date.now() + Math.random();
    setItems((p) => [...p, { id, msg, kind }]);
    setTimeout(() => setItems((p) => p.filter((t) => t.id !== id)), 5000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`rounded border bg-panel px-4 py-3 text-sm shadow ${t.kind === "error" ? "border-bad text-bad" : "border-ok text-ok"}`}>{t.msg}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
