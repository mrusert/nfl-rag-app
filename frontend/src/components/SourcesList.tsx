/**
 * Collapsible sources list component.
 */

import { useState } from 'react';
import type { SourceInfo } from '../types/api';

interface SourcesListProps {
  sources: SourceInfo[];
}

function SourceCard({ source, index }: { source: SourceInfo; index: number }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const metadata = source.metadata;
  const team = metadata.team as string | undefined;
  const season = metadata.season as number | undefined;
  const week = metadata.week as number | undefined;
  const playerName = metadata.player_name as string | undefined;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center text-xs font-medium text-gray-600 bg-gray-100 rounded-full">
            {index + 1}
          </span>
          <div>
            <span className="text-sm font-medium text-gray-900 capitalize">
              {source.chunk_type.replace(/_/g, ' ')}
            </span>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              {team && <span>{team}</span>}
              {season && <span>Season {season}</span>}
              {week && <span>Week {week}</span>}
              {playerName && <span>{playerName}</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            Score: {(source.score * 100).toFixed(1)}%
          </span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${
              isExpanded ? 'rotate-180' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">
            {source.preview}
          </p>
          <div className="mt-3 text-xs text-gray-400">
            ID: {source.chunk_id}
          </div>
        </div>
      )}
    </div>
  );
}

export function SourcesList({ sources }: SourcesListProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (sources.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 mb-3"
      >
        <svg
          className={`w-4 h-4 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        Sources ({sources.length})
      </button>

      {!isCollapsed && (
        <div className="space-y-2">
          {sources.map((source, index) => (
            <SourceCard key={source.chunk_id} source={source} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}
