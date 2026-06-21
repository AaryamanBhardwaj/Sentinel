import { useState } from "react";
import { analyze, type Diagnosis } from "./lib/api";
import { useHistory, type HistoryEntry } from "./hooks/useHistory";
import { InputPanel } from "./components/InputPanel";
import { ResultPanel } from "./components/ResultPanel";
import { HistorySidebar } from "./components/HistorySidebar";

export default function App() {
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { entries, addEntry, clearHistory } = useHistory();

  const handleSubmit = async (input: string) => {
    setIsLoading(true);
    setError(null);
    setDiagnosis(null);

    try {
      const result = await analyze(input);
      setDiagnosis(result);
      addEntry(input, result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleHistorySelect = (entry: HistoryEntry) => {
    setDiagnosis(entry.diagnosis);
    setError(null);
  };

  return (
    <div className="app">
      <header>
        <h1>
          <span className="logo">⚡</span> RootCause
        </h1>
        <p className="subtitle">AI SRE Agent — paste a stack trace, get a diagnosis</p>
      </header>

      <div className="main-layout">
        <main>
          <InputPanel onSubmit={handleSubmit} isLoading={isLoading} />
          <ResultPanel
            diagnosis={diagnosis}
            error={error}
            isLoading={isLoading}
          />
        </main>
        <HistorySidebar
          entries={entries}
          onSelect={handleHistorySelect}
          onClear={clearHistory}
        />
      </div>
    </div>
  );
}
