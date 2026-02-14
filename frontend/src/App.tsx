import { useState } from 'react';
import { QueryInput } from './components/QueryInput';
import { AnswerDisplay } from './components/AnswerDisplay';
import { FilterPanel } from './components/FilterPanel';
import { HealthStatus } from './components/HealthStatus';
import { LoadingSpinner } from './components/LoadingSpinner';
import { useAgentMutation } from './hooks/useAgent';
import type { AgentResponse, SearchFilters } from './types/api';

interface HistoryItem {
  query: string;
  response: AgentResponse;
  timestamp: Date;
}

function App() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [filters, setFilters] = useState<SearchFilters>({});
  const agentMutation = useAgentMutation();

  const handleSubmit = async (query: string) => {
    try {
      const response = await agentMutation.mutateAsync({
        question: query,
      });

      setHistory((prev) => [
        { query, response, timestamp: new Date() },
        ...prev,
      ]);
    } catch (error) {
      console.error('Query failed:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/football.svg" alt="NFL RAG" className="w-8 h-8" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">NFL RAG</h1>
              <p className="text-xs text-gray-500">AI-Powered NFL Stats</p>
            </div>
          </div>
          <HealthStatus />
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Query input */}
        <div className="mb-8">
          <QueryInput
            onSubmit={handleSubmit}
            isLoading={agentMutation.isPending}
            placeholder="Ask about NFL stats, players, games, weather conditions..."
          />
        </div>

        {/* Filters (collapsible) */}
        <div className="mb-6">
          <FilterPanel filters={filters} onFiltersChange={setFilters} />
        </div>

        {/* Loading state */}
        {agentMutation.isPending && (
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-3">
              <LoadingSpinner size="lg" className="text-blue-600" />
              <p className="text-sm text-gray-500">Searching and generating answer...</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {agentMutation.isError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-red-700">
              {agentMutation.error?.message || 'An error occurred while processing your query.'}
            </p>
          </div>
        )}

        {/* Results */}
        {history.length > 0 && !agentMutation.isPending && (
          <div className="space-y-8">
            {history.map((item, index) => (
              <div key={index} className="space-y-4">
                {/* User query */}
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <svg
                      className="w-4 h-4 text-blue-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
                    </svg>
                  </div>
                  <div className="flex-1 bg-blue-50 rounded-lg px-4 py-3">
                    <p className="text-gray-800">{item.query}</p>
                  </div>
                </div>

                {/* Assistant response */}
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                    <svg
                      className="w-4 h-4 text-gray-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <AnswerDisplay response={item.response} />
                  </div>
                </div>

                {index < history.length - 1 && (
                  <hr className="border-gray-200" />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {history.length === 0 && !agentMutation.isPending && (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <svg
                className="w-8 h-8 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-medium text-gray-900 mb-2">
              Ask a Question
            </h2>
            <p className="text-gray-500 max-w-md mx-auto mb-6">
              Search through 12 years of NFL data including player stats, game results,
              weather conditions, and betting lines.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {[
                'How did Patrick Mahomes perform in cold weather games?',
                'What was the highest scoring game in 2023?',
                'Compare Tom Brady and Aaron Rodgers playoff stats',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSubmit(suggestion)}
                  className="px-3 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-auto">
        <div className="max-w-4xl mx-auto px-4 py-4 text-center text-xs text-gray-500">
          NFL RAG - Powered by local LLMs and ChromaDB
        </div>
      </footer>
    </div>
  );
}

export default App;
