/**
 * Answer display component for showing LLM responses.
 */

import type { QueryResponse } from '../types/api';

interface AnswerDisplayProps {
  response: QueryResponse;
}

export function AnswerDisplay({ response }: AnswerDisplayProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      {/* Answer */}
      <div className="prose prose-sm max-w-none">
        <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
          {response.answer}
        </div>
      </div>

      {/* Metadata footer */}
      <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-4 text-xs text-gray-500">
        <span>Model: {response.model}</span>
        <span>Retrieval: {response.retrieval_time_ms.toFixed(0)}ms</span>
        <span>Generation: {response.generation_time_ms.toFixed(0)}ms</span>
        <span>Total: {response.total_time_ms.toFixed(0)}ms</span>
      </div>
    </div>
  );
}
