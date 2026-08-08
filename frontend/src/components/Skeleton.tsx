export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-base-700 rounded ${className}`} />;
}
