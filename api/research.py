"""
Vercel Python API for the Business Research Agent.

This is exposed as a Flask app so Vercel can mount it as a Python entrypoint.
"""

import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any

from flask import Flask, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from business_research_agent.agent import (
        BusinessResearchGraph,
        get_gemini_model,
        search_duckduckgo,
    )
except ImportError:
    # Fallback if module structure differs
    from agent import (
        BusinessResearchGraph,
        get_gemini_model,
        search_duckduckgo,
    )

# Vercel reuses containers, so initialize the graph lazily once.
_graph = None
app = Flask(__name__)

def get_graph():
    """Lazy initialization of the graph to save cold start time"""
    global _graph
    if _graph is None:
        try:
            _graph = BusinessResearchGraph()
        except Exception as e:
            print(f"Error initializing graph: {str(e)}")
            _graph = None
    return _graph


def create_cors_headers() -> Dict[str, str]:
    """Create CORS headers for API responses"""
    return {
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,OPTIONS,PATCH,DELETE,POST,PUT',
        'Access-Control-Allow-Headers': 'X-CSRF-Token,X-Requested-With,Accept,Accept-Version,Content-Length,Content-MD5,Content-Type,Date,X-Api-Version',
        'Content-Type': 'application/json',
    }


@app.after_request
def add_cors_headers(response):
    """Attach CORS headers to every response."""
    for key, value in create_cors_headers().items():
        response.headers[key] = value
    return response


def validate_query(query: str) -> tuple[bool, Optional[str]]:
    """Validate query input"""
    if not query:
        return False, "Query is required"
    
    query = query.strip()
    if not query:
        return False, "Query cannot be empty"
    
    if len(query) > 1000:
        return False, "Query too long (max 1000 characters)"
    
    if len(query) < 3:
        return False, "Query too short (min 3 characters)"
    
    return True, None


@app.route('/', methods=['POST', 'OPTIONS'])
def research():
    """Handle research requests from the Vercel frontend."""
    start_time = datetime.now()
    
    try:
        # Handle CORS preflight
        if request.method == 'OPTIONS':
            return ('', 200)
        
        # Only accept POST
        if request.method != 'POST':
            return jsonify({'error': 'Method not allowed. Use POST.'}), 405
        
        # Parse request body
        try:
            body = request.get_json(silent=True) or {}
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON in request body'}), 400
        
        # Extract and validate query
        query = body.get('query', '').strip() if body.get('query') else ''
        is_valid, error_msg = validate_query(query)
        
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Get or initialize graph
        graph = get_graph()
        
        if not graph:
            # Fallback: use search directly
            try:
                search_results = search_duckduckgo(query, max_results=5)
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return jsonify({
                    'success': True,
                    'response': f"Search results for '{query}':\n\n{search_results}",
                    'confidence': 5,
                    'sources': ['DuckDuckGo (Fallback)'],
                    'timestamp': datetime.now().isoformat(),
                    'execution_time_ms': execution_time,
                })
            except Exception as e:
                return jsonify({'error': f'System initialization failed: {str(e)}'}), 500
        
        # Run the research workflow
        try:
            initial_state = {
                "messages": [],
                "current_query": query,
                "clarity_status": None,
                "clarity_explanation": "",
                "clarification_prompt": "",
                "research_findings": "",
                "confidence_score": 0,
                "search_source": "",
                "research_attempts": 0,
                "validation_result": None,
                "validation_notes": "",
                "final_response": "",
                "conversation_context": "",
                "current_agent": "clarity",
                "max_research_attempts": 3,
            }
            
            # Invoke the graph
            result = graph.graph.invoke(initial_state)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Handle timeout (>9 seconds)
            if execution_time > 9000:
                print(f"Warning: Slow execution ({execution_time}ms)")
            
            return jsonify({
                'success': True,
                'response': result.get('final_response', ''),
                'confidence': float(result.get('confidence_score', 0)),
                'clarification_needed': result.get('clarity_status') == 'needs_clarification',
                'clarification_prompt': result.get('clarification_prompt', ''),
                'timestamp': datetime.now().isoformat(),
                'execution_time_ms': execution_time,
            })
        
        except Exception as agent_error:
            print(f"Agent Error: {str(agent_error)}")
            
            # Fallback: Simple search
            try:
                search_results = search_duckduckgo(query, max_results=5)
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return jsonify({
                    'success': True,
                    'response': f"Search results for '{query}':\n\n{search_results}\n\n(Note: Using fallback search mode)",
                    'confidence': 5,
                    'sources': ['DuckDuckGo (Fallback)'],
                    'timestamp': datetime.now().isoformat(),
                    'execution_time_ms': execution_time,
                })
            except Exception as search_error:
                raise Exception(f"Agent failed: {str(agent_error)}, Search failed: {str(search_error)}")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return jsonify({
            'error': str(e),
            'execution_time_ms': execution_time,
        }), 500


@app.route('/', methods=['GET'])
def health_check():
    """Simple health check so the function responds with JSON."""
    return jsonify({
        'success': True,
        'message': 'Business Research API is running',
    })
