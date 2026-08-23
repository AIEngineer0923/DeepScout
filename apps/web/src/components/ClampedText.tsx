export function ClampedText({
  children,
  lines = 2,
  className = "",
}: {
  children: string;
  lines?: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <span className={`clamped-text clamped-text-${lines} ${className}`.trim()}>
      {children}
    </span>
  );
}
