/**
 * Health status indicator component.
 */

import { useHealth } from '../hooks/useHealth';

export function HealthStatus() {
  const { data: health, isLoading, isError } = useHealth();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <div className="w-2 h-2 rounded-full bg-gray-400 animate-pulse" />
        <span>Connecting...</span>
      </div>
    );
  }

  if (isError || !health) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-600">
        <div className="w-2 h-2 rounded-full bg-red-500" />
        <span>API Offline</span>
      </div>
    );
  }

  const isHealthy = health.status === 'healthy';
  const statusColor = isHealthy ? 'bg-green-500' : 'bg-yellow-500';
  const textColor = isHealthy ? 'text-green-700' : 'text-yellow-700';

  return (
    <div className={`flex items-center gap-2 text-sm ${textColor}`}>
      <div className={`w-2 h-2 rounded-full ${statusColor}`} />
      <span className="hidden sm:inline">
        {isHealthy ? 'Online' : 'Degraded'}
      </span>
      <span className="hidden md:inline text-gray-500">
        ({health.chunk_count.toLocaleString()} chunks)
      </span>
    </div>
  );
}
