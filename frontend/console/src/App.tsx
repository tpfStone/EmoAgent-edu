import { useState } from "react";
import styles from "./App.module.css";
import { BatchEvidence } from "./components/BatchEvidence";
import { ConsoleRail, type ConsoleTab } from "./components/ConsoleRail";
import { FrameworkMap } from "./components/FrameworkMap";
import { SingleTurnTrace } from "./components/SingleTurnTrace";

export default function App() {
  const [activeTab, setActiveTab] = useState<ConsoleTab>("single");

  return (
    <main className={styles.shell}>
      <ConsoleRail activeTab={activeTab} onTabChange={setActiveTab} />
      <section className={styles.workspace} aria-label="Research console workspace">
        {activeTab === "single" && <SingleTurnTrace />}
        {activeTab === "batch" && <BatchEvidence />}
        {activeTab === "framework" && <FrameworkMap />}
      </section>
    </main>
  );
}
