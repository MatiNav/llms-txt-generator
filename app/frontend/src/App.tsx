import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createRun,
  fetchRunDownloads,
  fetchSites,
  RenderMode,
  RunDownloadsResponse,
  SiteResponse,
} from "./api/client";
import { useRunLifecycle } from "./hooks/useRunLifecycle";

function formatStageLabel(stageName: string): string {
  switch (stageName) {
    case "discovering":
      return "Discovering pages";
    case "fetching":
      return "Fetching pages";
    case "processing":
      return "Processing content";
    case "llm_generation":
      return "LLM generation";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return stageName;
  }
}

function formatCompletedReasonLabel(completedReason: string | null): string {
  if (completedReason === "unchanged_root") {
    return "Completed — no root changes detected";
  }
  return "Completed — artifacts regenerated";
}

export function App() {
  const [targetUrl, setTargetUrl] = useState("");
  const [renderMode, setRenderMode] = useState<RenderMode>("http");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<RunDownloadsResponse | null>(null);
  const [sites, setSites] = useState<SiteResponse[]>([]);

  const {
    currentRunStatus,
    timelineEvents,
    sseDisconnected,
    lifecycleError,
    isFinished,
  } = useRunLifecycle(activeRunId);

  useEffect(() => {
    let isDisposed = false;

    fetchSites()
      .then((siteList) => {
        if (!isDisposed) {
          setSites(siteList);
        }
      })
      .catch(() => {
        if (!isDisposed) {
          setSites([]);
        }
      });

    return () => {
      isDisposed = true;
    };
  }, []);

  const canSubmit = () => {
    return targetUrl.trim().length > 0 && !isSubmitting;
  };

  const canRequestDownloads = useMemo(() => {
    if (activeRunId === null || currentRunStatus === null) {
      return false;
    }

    return currentRunStatus.stage === "completed";
  }, [activeRunId, currentRunStatus]);

  async function handleGenerateSubmit(submitEvent: FormEvent<HTMLFormElement>) {
    submitEvent.preventDefault();
    if (!canSubmit) {
      return;
    }

    setSubmitError(null);
    setDownloadError(null);
    setDownloads(null);
    setIsSubmitting(true);

    try {
      const generateResponse = await createRun({
        url: targetUrl.trim(),
        renderMode,
      });
      setActiveRunId(generateResponse.run_id);
    } catch (generationError) {
      const errorMessage =
        generationError instanceof Error
          ? generationError.message
          : "Failed to start generation";
      setSubmitError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLoadDownloads() {
    if (!canRequestDownloads || activeRunId === null) {
      return;
    }
    setDownloadError(null);
    try {
      const runDownloads = await fetchRunDownloads(activeRunId);
      setDownloads(runDownloads);
    } catch (downloadsRequestError) {
      const errorMessage =
        downloadsRequestError instanceof Error
          ? downloadsRequestError.message
          : "Failed to load download links";
      setDownloadError(errorMessage);
    }
  }

  return (
    <main className="page-shell">
      <section className="panel">
        <h1>llms.txt generator</h1>
        <p className="panel-subtitle">
          Enter a URL, choose render mode, and follow the full generation story.
        </p>

        <form className="generate-form" onSubmit={handleGenerateSubmit}>
          <label className="field-label" htmlFor="target-url">
            Website URL
          </label>
          <input
            id="target-url"
            className="text-input"
            placeholder="https://example.com/docs"
            value={targetUrl}
            onChange={(changeEvent) => setTargetUrl(changeEvent.target.value)}
          />

          <label className="field-label" htmlFor="render-mode">
            Render mode
          </label>
          <select
            id="render-mode"
            className="select-input"
            value={renderMode}
            onChange={(changeEvent) =>
              setRenderMode(changeEvent.target.value as RenderMode)
            }
          >
            <option value="http">http</option>
            <option value="spa">spa</option>
          </select>

          <button className="primary-button" disabled={!canSubmit} type="submit">
            {isSubmitting ? "Starting..." : "Generate"}
          </button>
        </form>

        {submitError !== null && <p className="error-text">{submitError}</p>}
      </section>

      <section className="panel">
        <h2>Run status</h2>
        {activeRunId === null && <p>No run started yet.</p>}

        {activeRunId !== null && (
          <>
            <p>
              <strong>Run:</strong> {activeRunId}
            </p>
            {currentRunStatus !== null && (
              <>
                <p>
                  <strong>Stage:</strong> {formatStageLabel(currentRunStatus.stage)}
                </p>
                {currentRunStatus.stage === "completed" && (
                  <p>
                    <strong>Outcome:</strong>{" "}
                    {formatCompletedReasonLabel(currentRunStatus.completed_reason)}
                  </p>
                )}
                <p>
                  <strong>Pages detected:</strong> {currentRunStatus.pages_detected}
                </p>
                <p>
                  <strong>Pages completed:</strong> {currentRunStatus.pages_completed} / {currentRunStatus.pages_queued}
                </p>
                {currentRunStatus.error_message !== null && (
                  <p className="error-text">{currentRunStatus.error_message}</p>
                )}
              </>
            )}

            {sseDisconnected && (
              <p className="warn-text">
                Live stream disconnected. Fallback polling is active.
              </p>
            )}

            {lifecycleError !== null && <p className="error-text">{lifecycleError}</p>}

            <div className="timeline-container">
              <h3>Timeline</h3>
              <ul className="timeline-list">
                {timelineEvents.map((timelineEvent, eventIndex) => (
                  <li key={`${timelineEvent.timestamp}-${eventIndex}`}>
                    <span className="timeline-event-name">{timelineEvent.eventName}</span>
                    <span className="timeline-event-stage">
                      {formatStageLabel(timelineEvent.payload.stage)}
                    </span>
                    <span className="timeline-event-time">{timelineEvent.timestamp}</span>
                  </li>
                ))}
              </ul>
            </div>

            {isFinished && (
              <div className="downloads-block">
                {canRequestDownloads ? (
                  <button className="secondary-button" onClick={handleLoadDownloads}>
                    Load download links
                  </button>
                ) : (
                  <p>
                    Downloads are only available for successfully completed runs.
                  </p>
                )}
                {downloadError !== null && (
                  <p className="error-text">{downloadError}</p>
                )}
                {downloads !== null && (
                  <ul className="downloads-list">
                    <li>
                      <a href={downloads.bundle_zip_url} target="_blank" rel="noreferrer">
                        Download bundle.zip
                      </a>
                    </li>
                  </ul>
                )}
              </div>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <h2>Recent sites</h2>
        {sites.length === 0 ? (
          <p>No sites yet.</p>
        ) : (
          <ul className="sites-list">
            {sites.map((siteEntry) => (
              <li key={siteEntry.site_id}>{siteEntry.root_url}</li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
