import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { analyzeBatch, getJob } from "./api";

const JobContext = createContext(null);

export function JobProvider({ children }) {
  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollJob = useCallback(
    (jobId) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const j = await getJob(jobId);
          setJob(j);
          if (j.status === "completed" || j.status === "failed") {
            stopPolling();
          }
        } catch (e) {
          stopPolling();
        }
      }, 2500);
    },
    [stopPolling]
  );

  // symbols = null -> "Analyze All", or array of symbol_codes -> "Analyze Selected"
  const startBatchJob = useCallback(
    async (symbols = null) => {
      const j = await analyzeBatch(symbols);
      setJob(j);
      pollJob(j.id);
      return j;
    },
    [pollJob]
  );

  useEffect(() => stopPolling, [stopPolling]);

  const isRunning = job && (job.status === "pending" || job.status === "running");

  return (
    <JobContext.Provider value={{ job, isRunning, startBatchJob }}>
      {children}
    </JobContext.Provider>
  );
}

export function useJob() {
  const ctx = useContext(JobContext);
  if (!ctx) throw new Error("useJob must be used within JobProvider");
  return ctx;
}
