/**
 * Answer display component for showing Agent responses.
 *
 * Includes feedback UI for rating answers and providing corrections.
 */

import { useState } from 'react';
import type { AgentResponse } from '../types/api';
import { submitFeedback } from '../api/client';

interface AnswerDisplayProps {
  response: AgentResponse;
}

type FeedbackState = 'none' | 'correct' | 'incorrect' | 'partial' | 'submitting' | 'submitted';

export function AnswerDisplay({ response }: AnswerDisplayProps) {
  const [showTools, setShowTools] = useState(false);
  const [feedbackState, setFeedbackState] = useState<FeedbackState>('none');
  const [showCorrectionForm, setShowCorrectionForm] = useState(false);
  const [correctAnswer, setCorrectAnswer] = useState('');
  const [notes, setNotes] = useState('');

  // Submit feedback to the API
  const handleFeedback = async (rating: 'correct' | 'incorrect' | 'partial') => {
    if (!response.feedback_entry_id) {
      console.error('No feedback_entry_id available');
      return;
    }

    // For incorrect/partial, show the correction form first
    if ((rating === 'incorrect' || rating === 'partial') && !showCorrectionForm) {
      setShowCorrectionForm(true);
      setFeedbackState(rating);
      return;
    }

    setFeedbackState('submitting');

    try {
      await submitFeedback({
        entry_id: response.feedback_entry_id,
        rating,
        correct_answer: correctAnswer || undefined,
        notes: notes || undefined,
      });
      setFeedbackState('submitted');
      setShowCorrectionForm(false);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
      setFeedbackState('none');
    }
  };

  // Cancel the correction form
  const handleCancel = () => {
    setShowCorrectionForm(false);
    setFeedbackState('none');
    setCorrectAnswer('');
    setNotes('');
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      {/* Answer */}
      <div className="prose prose-sm max-w-none">
        <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
          {response.answer}
        </div>
      </div>

      {/* Feedback UI */}
      {response.feedback_entry_id && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          {feedbackState === 'submitted' ? (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Thanks for your feedback!
            </div>
          ) : feedbackState === 'submitting' ? (
            <div className="text-sm text-gray-500">Submitting feedback...</div>
          ) : showCorrectionForm ? (
            <div className="space-y-3">
              <p className="text-sm text-gray-700">
                {feedbackState === 'incorrect' ? 'What is the correct answer?' : 'What was partially wrong?'}
              </p>
              <textarea
                value={correctAnswer}
                onChange={(e) => setCorrectAnswer(e.target.value)}
                placeholder="Enter the correct answer..."
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
              />
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional notes (optional)..."
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={2}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => handleFeedback(feedbackState as 'incorrect' | 'partial')}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Submit
                </button>
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">Was this answer helpful?</span>
              <div className="flex gap-2">
                <button
                  onClick={() => handleFeedback('correct')}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-green-50 hover:border-green-300 transition-colors"
                  title="Correct"
                >
                  <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                  </svg>
                  Correct
                </button>
                <button
                  onClick={() => handleFeedback('partial')}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-yellow-50 hover:border-yellow-300 transition-colors"
                  title="Partially correct"
                >
                  <svg className="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  Partial
                </button>
                <button
                  onClick={() => handleFeedback('incorrect')}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-red-50 hover:border-red-300 transition-colors"
                  title="Incorrect"
                >
                  <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                  </svg>
                  Wrong
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Metadata footer */}
      <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-4 text-xs text-gray-500">
        <span>Model: {response.model}</span>
        {response.iterations > 0 && (
          <span>Iterations: {response.iterations}</span>
        )}
        <span>Total: {response.total_time_ms.toFixed(0)}ms</span>
        {response.tool_calls && response.tool_calls.length > 0 && (
          <button
            onClick={() => setShowTools(!showTools)}
            className="text-blue-600 hover:text-blue-800 underline"
          >
            {showTools ? 'Hide' : 'Show'} tools ({response.tool_calls.length})
          </button>
        )}
      </div>

      {/* Tool calls (collapsible) */}
      {showTools && response.tool_calls && response.tool_calls.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <h4 className="text-xs font-medium text-gray-700 mb-2">Tools Used:</h4>
          <div className="space-y-2">
            {response.tool_calls.map((tool, index) => (
              <div
                key={index}
                className={`text-xs p-2 rounded ${
                  tool.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
                }`}
              >
                <div className="font-medium">
                  {tool.tool}
                  {tool.success ? (
                    <span className="ml-2 text-green-600">✓</span>
                  ) : (
                    <span className="ml-2 text-red-600">✗</span>
                  )}
                </div>
                <div className="text-gray-500 mt-1">
                  Args: {JSON.stringify(tool.arguments)}
                </div>
                {tool.error && (
                  <div className="text-red-600 mt-1">Error: {tool.error}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
