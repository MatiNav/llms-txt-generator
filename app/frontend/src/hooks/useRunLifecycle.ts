import { useEffect, useMemo, useRef, useState } from "react";

import {
  connectRunEvents,
  RunStatusResponse,
} from "../api/client";

export type TimelineEvent = {
  eventName: string;
  timestamp: string;
  payload: RunStatusResponse;
};

const terminalStages = new Set(["completed", "failed"]);
const sseRotationIntervalMs = 105_000; // app runner server closes it at 120

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

    const runId = activeRunId;

    let isDisposed = false;
    let eventSource: EventSource | null = null;
    let rotationIntervalId: number | null = null;
    const eventNames = [
      "run.discovering",
      "run.fetch_progress",
      "run.processing",
      "run.llm_generation",
      "run.completed",
      "run.failed",
    ];
    let listeners: Array<{
      eventName: string;
      eventHandler: (messageEvent: MessageEvent<string>) => void;
    }> = [];

    function closeStream(): void {
      if (eventSource === null) {
        return;
      }
      listeners.forEach(({ eventName, eventHandler }) => {
        eventSource?.removeEventListener(eventName, eventHandler);
      });
      listeners = [];
      eventSource.onerror = null;
      eventSource.close();
      eventSource = null;
    }

    function upsertStatus(eventName: string, runStatus: RunStatusResponse): void {
      const statusFingerprint = createStableFingerprint(runStatus);
      if (statusFingerprint === lastFingerprintRef.current) {
        return;
      }

      lastFingerprintRef.current = statusFingerprint;
      setCurrentRunStatus(runStatus);
      reachedTerminalStageRef.current = isTerminalStatus(runStatus);
      setTimelineEvents((previousTimelineEvents) => {
        if (eventName !== "run.fetch_progress") {
          const newTimestamp = new Date().toISOString();
          return [
            ...previousTimelineEvents.map((timelineEvent) =>
              timelineEvent.eventName === "run.fetch_progress" &&
              runStatus.pages_completed > timelineEvent.payload.pages_completed
                ? {
                    ...timelineEvent,
                    timestamp: newTimestamp,
                    payload: runStatus,
                  }
                : timelineEvent
            ),
            {
              eventName,
              timestamp: newTimestamp,
              payload: runStatus,
            },
          ];
        }

        const existingFetchTimelineIndex = previousTimelineEvents.findIndex(
          (timelineEvent) => timelineEvent.eventName === "run.fetch_progress"
        );

        if (existingFetchTimelineIndex < 0) {
          return [
            ...previousTimelineEvents,
            {
              eventName,
              timestamp: new Date().toISOString(),
              payload: runStatus,
            },
          ];
        }

        const updatedTimelineEvents = [...previousTimelineEvents];
        updatedTimelineEvents[existingFetchTimelineIndex] = {
          ...updatedTimelineEvents[existingFetchTimelineIndex],
          timestamp: new Date().toISOString(),
          payload: runStatus,
        };
        return updatedTimelineEvents;
      });
    }

    function handleTypedEvent(eventName: string) {
      return (messageEvent: MessageEvent<string>) => {
        if (isDisposed) {
          return;
        }
        try {
          const parsedPayload = JSON.parse(messageEvent.data) as RunStatusResponse;
          upsertStatus(eventName, parsedPayload);
          if (isTerminalStatus(parsedPayload)) {
            closeStream();
          }
        } catch {
          setLifecycleError("Failed to parse event stream payload");
        }
      };
    }

    function openStream(): void {
      closeStream();
      eventSource = connectRunEvents(runId);
      listeners = eventNames.map((eventName) => {
        const eventHandler = handleTypedEvent(eventName);
        eventSource?.addEventListener(eventName, eventHandler);
        return { eventName, eventHandler };
      });

      eventSource.onerror = () => {
        if (isDisposed) {
          return;
        }

        if (reachedTerminalStageRef.current) {
          closeStream();
          return;
        }

        openStream();
      };
    }

    openStream();

    rotationIntervalId = window.setInterval(() => {
      if (isDisposed) {
        return;
      }
      if (reachedTerminalStageRef.current) {
        return;
      }

      openStream();
    }, sseRotationIntervalMs);

    return () => {
      isDisposed = true;
      closeStream();
      if (rotationIntervalId !== null) {
        window.clearInterval(rotationIntervalId);
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
