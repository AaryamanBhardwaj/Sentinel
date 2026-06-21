import { useState, useCallback } from "react";
import type { Diagnosis } from "../lib/api";

export interface HistoryEntry {
  id: string;
  input: string;
  diagnosis: Diagnosis;
  timestamp: number;
}

const STORAGE_KEY = "rootcause_history";
const MAX_ENTRIES = 20;

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
}

export function useHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>(loadHistory);

  const addEntry = useCallback((input: string, diagnosis: Diagnosis) => {
    const entry: HistoryEntry = {
      id: crypto.randomUUID(),
      input,
      diagnosis,
      timestamp: Date.now(),
    };
    setEntries((prev) => {
      const next = [entry, ...prev].slice(0, MAX_ENTRIES);
      saveHistory(next);
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setEntries([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { entries, addEntry, clearHistory };
}
