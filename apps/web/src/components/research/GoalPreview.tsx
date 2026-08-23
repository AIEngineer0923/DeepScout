export function GoalPreview({
  children,
  lines = 2,
  className = "",
}: {
  children: string;
  lines?: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <span className={`goal-preview goal-preview-${lines} ${className}`.trim()}>
      {children}
    </span>
  );
}
