import { useEffect, useState, type ReactNode } from "react";
import styles from "./TransitionSlot.module.css";

type TransitionState = "entering" | "entered" | "exiting";

interface TransitionSlotProps {
  children: ReactNode;
  className?: string;
  viewKey: string;
}

export function TransitionSlot({
  children,
  className,
  viewKey,
}: TransitionSlotProps) {
  const [transitionState, setTransitionState] =
    useState<TransitionState>("entered");

  useEffect(() => {
    setTransitionState("entering");

    const frame = window.requestAnimationFrame(() => {
      setTransitionState("entered");
    });

    return () => window.cancelAnimationFrame(frame);
  }, [viewKey]);

  return (
    <div
      className={`${styles.slot} ${styles[transitionState]} ${className ?? ""}`}
      data-testid="student-main-transition"
      data-transition-key={viewKey}
      data-transition-state={transitionState}
    >
      {children}
    </div>
  );
}
