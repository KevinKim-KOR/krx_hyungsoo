"use client";

type AppLoadingStateProps = {
  label?: string;
  compact?: boolean;
};

export function AppLoadingState({
  label = "데이터를 불러오는 중...",
  compact = false,
}: AppLoadingStateProps) {
  return (
    <div className={compact ? "appLoadingState appLoadingStateCompact" : "appLoadingState"} role="status" aria-live="polite">
      <div className="appLoadingBar" aria-hidden="true">
        <span className="appLoadingBarTrack" />
      </div>
      <div className="appLoadingLabel">{label}</div>
    </div>
  );
}
