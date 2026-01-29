/**
 * Filter panel component for search filtering.
 */

import { useState } from 'react';
import { useTeams } from '../hooks/useHealth';
import type { SearchFilters } from '../types/api';

interface FilterPanelProps {
  filters: SearchFilters;
  onFiltersChange: (filters: SearchFilters) => void;
}

const CHUNK_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'game_summary', label: 'Game Summary' },
  { value: 'player_stats', label: 'Player Stats' },
  { value: 'team_game', label: 'Team Game' },
  { value: 'weather', label: 'Weather' },
];

const SEASONS = Array.from({ length: 12 }, (_, i) => 2014 + i);

export function FilterPanel({ filters, onFiltersChange }: FilterPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: teamsData } = useTeams();

  // Flatten teams into a simple list
  const teamsList: { abbr: string; name: string }[] = [];
  if (teamsData) {
    Object.values(teamsData).forEach((division) => {
      Object.entries(division).forEach(([abbr, name]) => {
        teamsList.push({ abbr, name });
      });
    });
    teamsList.sort((a, b) => a.name.localeCompare(b.name));
  }

  const hasActiveFilters = !!(filters.team || filters.season || filters.chunk_type);

  const handleClear = () => {
    onFiltersChange({});
  };

  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
            />
          </svg>
          <span className="text-sm font-medium text-gray-700">Filters</span>
          {hasActiveFilters && (
            <span className="px-2 py-0.5 text-xs font-medium text-blue-700 bg-blue-100 rounded-full">
              Active
            </span>
          )}
        </div>
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
      </button>

      {isExpanded && (
        <div className="px-4 py-3 border-t border-gray-200 space-y-4">
          {/* Team filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Team
            </label>
            <select
              value={filters.team || ''}
              onChange={(e) =>
                onFiltersChange({ ...filters, team: e.target.value || undefined })
              }
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Teams</option>
              {teamsList.map((team) => (
                <option key={team.abbr} value={team.abbr}>
                  {team.name} ({team.abbr})
                </option>
              ))}
            </select>
          </div>

          {/* Season filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Season
            </label>
            <select
              value={filters.season || ''}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  season: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Seasons</option>
              {SEASONS.map((season) => (
                <option key={season} value={season}>
                  {season}
                </option>
              ))}
            </select>
          </div>

          {/* Chunk type filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Data Type
            </label>
            <select
              value={filters.chunk_type || ''}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  chunk_type: e.target.value || undefined,
                })
              }
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {CHUNK_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Clear button */}
          {hasActiveFilters && (
            <button
              onClick={handleClear}
              className="w-full px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              Clear Filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
