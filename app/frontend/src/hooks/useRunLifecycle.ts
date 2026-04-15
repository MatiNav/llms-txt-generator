import { useEffect, useMemo, useRef, useState } from "react";

import {
  connectRunEvents,
  fetchRunStatus,
  RunStatusResponse,
} from "../api/client";

export type TimelineEvent = {
  eventName: string;
  timestamp: string;
  payload: RunStatusResponse;
};

const terminalStages = new Set(["completed", "failed"]);

function createStableFingerprint(runStatus: RunStatusResponse): string {
  return JSON.stringify({
    runId: runStatus.run_id,
    state: runStatus.state,
    stage: runStatus.stage,
    pagesDetected: runStatus.pages_detected,
    pagesQueued: runStatus.pages_queued,
    pagesCompleted: runStatus.pages_completed,
    completedReason: runStatus.completed_reason,
    errorMessage: runStatus.error_message,
  });
}

function isTerminalStatus(runStatus: RunStatusResponse): boolean {
  return terminalStages.has(runStatus.stage);
}

export function useRunLifecycle(activeRunId: string | null) {
  const [currentRunStatus, setCurrentRunStatus] =
    useState<RunStatusResponse | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [sseDisconnected, setSseDisconnected] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const lastFingerprintRef = useRef<string | null>(null);
  const reachedTerminalStageRef = useRef(false);

  useEffect(() => {
    setCurrentRunStatus(null);
    setTimelineEvents([]);
    setSseDisconnected(false);
    setLifecycleError(null);
    lastFingerprintRef.current = null;
    reachedTerminalStageRef.current = false;

    if (activeRunId === null) {
      return;
    }

    let isDisposed = false;
    let pollingIntervalId: number | null = null;
    const eventSource = connectRunEvents(activeRunId);

    function appendStatus(eventName: string, runStatus: RunStatusResponse): void {
      const statusFingerprint = createStableFingerprint(runStatus);
      if (statusFingerprint === lastFingerprintRef.current) {
        return;
      }

      lastFingerprintRef.current = statusFingerprint;
      setCurrentRunStatus(runStatus);
      reachedTerminalStageRef.current = isTerminalStatus(runStatus);
      setTimelineEvents((previousTimelineEvents) => [
        ...previousTimelineEvents,
        {
          eventName,
          timestamp: new Date().toISOString(),
          payload: runStatus,
        },
      ]);
    }

    function handleTypedEvent(eventName: string) {
      return (messageEvent: MessageEvent<string>) => {
        if (isDisposed) {
          return;
        }
        try {
          const parsedPayload = JSON.parse(messageEvent.data) as RunStatusResponse;
          appendStatus(eventName, parsedPayload);
          if (isTerminalStatus(parsedPayload)) {
            eventSource.close();
          }
        } catch {
          setLifecycleError("Failed to parse event stream payload");
        }
      };
    }

    const eventNames = [
      "run.discovering",
      "run.fetch_progress",
      "run.processing",
      "run.llm_generation",
      "run.completed",
      "run.failed",
    ];
    const listeners = eventNames.map((eventName) => {
      const eventHandler = handleTypedEvent(eventName);
      eventSource.addEventListener(eventName, eventHandler);
      return { eventName, eventHandler };
    });

    eventSource.onerror = () => {
      if (isDisposed) {
        return;
      }

      if (reachedTerminalStageRef.current) {
        eventSource.close();
        return;
      }

      setSseDisconnected(true);
      eventSource.close();
      if (pollingIntervalId !== null) {
        return;
      }

      pollingIntervalId = window.setInterval(async () => {
        if (isDisposed || activeRunId === null) {
          return;
        }
        try {
          const latestRunStatus = await fetchRunStatus(activeRunId);
          appendStatus("run.polling", latestRunStatus);
          if (isTerminalStatus(latestRunStatus) && pollingIntervalId !== null) {
            window.clearInterval(pollingIntervalId);
            pollingIntervalId = null;
          }
        } catch {
          setLifecycleError("Failed to poll run status after stream disconnect");
        }
      }, 2000);
    };

    return () => {
      isDisposed = true;
      listeners.forEach(({ eventName, eventHandler }) => {
        eventSource.removeEventListener(eventName, eventHandler);
      });
      eventSource.close();
      if (pollingIntervalId !== null) {
        window.clearInterval(pollingIntervalId);
      }
    };
  }, [activeRunId]);

  const isFinished = useMemo(() => {
    if (currentRunStatus === null) {
      return false;
    }
    return isTerminalStatus(currentRunStatus);
  }, [currentRunStatus]);

  return {
    currentRunStatus,
    timelineEvents,
    sseDisconnected,
    lifecycleError,
    isFinished,
  };
}
