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
        AgentState,
        search_duckduckgo,
    )
except Exception as _import_err:
    print(f"Warning: failed to import business_research_agent.agent: {_import_err}")
    BusinessResearchGraph = None

    class AgentState:  # minimal fallback used only for request shaping when agent unavailable
        def __init__(self, messages=None):
            self.messages = messages or []
            self.current_query = ""
            self.conversation_context = ""
            self.clarification_prompt = ""
            self.search_source = ""

    def search_duckduckgo(query: str, max_results: int = 5):
        return f"DuckDuckGo search unavailable in this deployment (import error: {_import_err})"

from langchain_core.messages import HumanMessage, AIMessage

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


def debug_headers(mode: str, query: str = '', status: str = '', preview: str = '') -> Dict[str, str]:
    """Attach lightweight debugging metadata to responses."""
    headers = {
        'X-Response-Mode': mode,
    }

    if query:
        headers['X-Debug-Query'] = query[:80]

    if status:
        headers['X-Debug-Status'] = status[:80]

    if preview:
        headers['X-Debug-Preview'] = preview[:200]

    return headers


@app.after_request
def add_cors_headers(response):
    """Attach CORS headers to every response."""
    for key, value in create_cors_headers().items():
        response.headers[key] = value
    return response


@app.after_request
def add_debug_headers(response):
    """Attach debug headers when present on the response object."""
    debug = getattr(response, '_debug_headers', None)
    if isinstance(debug, dict):
        for key, value in debug.items():
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
@app.route('/api/research', methods=['POST', 'OPTIONS'])
def research():
    """Handle research requests from the Vercel frontend."""
    from dotenv import load_dotenv
    from langchain_core.messages import HumanMessage, AIMessage

    load_dotenv()
    start_time = datetime.now()

    try:
        if request.method == 'OPTIONS':
            response = jsonify({'success': True, 'message': 'CORS preflight ok'})
            response._debug_headers = debug_headers('preflight')
            return response, 200

        if request.method != 'POST':
            response = jsonify({'error': 'Method not allowed. Use POST.'})
            response._debug_headers = debug_headers('error', status='method-not-allowed')
            return response, 405

        body = request.get_json(silent=True) or {}
        query = body.get('query', '').strip() if body.get('query') else ''
        is_valid, error_msg = validate_query(query)
        if not is_valid:
            response = jsonify({'error': error_msg})
            response._debug_headers = debug_headers('error', query=query, status=error_msg)
            return response, 400

        previous_messages = body.get('previous_messages', [])
        conversation_messages = []
        if isinstance(previous_messages, list):
            for message in previous_messages[-12:]:
                if not isinstance(message, dict):
                    continue
                content = str(message.get('content', '')).strip()
                if not content:
                    continue
                role = str(message.get('role') or message.get('type') or 'user').lower()
                if role == 'assistant':
                    conversation_messages.append(AIMessage(content=content))
                else:
                    conversation_messages.append(HumanMessage(content=content))

        state = AgentState(messages=conversation_messages)
        state.current_query = query
        if conversation_messages:
            state.conversation_context = " ".join(
                msg.content for msg in conversation_messages[-4:]
                if hasattr(msg, 'content') and msg.content
            )

        graph = get_graph()
        if graph is None:
            search_results = search_duckduckgo(query, max_results=5)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            response = jsonify({
                'success': True,
                'response': f"Search results for '{query}':\n\n{search_results}\n\n(Note: Gemini graph could not initialize on this deployment.)",
                'confidence': 5,
                'sources': ['DuckDuckGo (Fallback)'],
                'timestamp': datetime.now().isoformat(),
                'execution_time_ms': execution_time,
            })
            response._debug_headers = debug_headers('fallback', query=query, status='graph-init-failed')
            return response, 200

        result = graph.process_query(query, state)
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        if result.get('status') != 'success':
            response = jsonify({
                'success': False,
                'error': result.get('error', 'The research workflow failed.'),
                'response': result.get('response', ''),
                'timestamp': datetime.now().isoformat(),
                'execution_time_ms': execution_time,
            })
            response._debug_headers = debug_headers('error', query=query, status='workflow-failed', preview=str(result.get('error', '')))
            return response, 500

        response = jsonify({
            'success': True,
            'response': result.get('response', ''),
            'confidence': float(result.get('confidence_score', 0.0)),
            'clarification_needed': bool(result.get('clarification_needed', False)),
            'clarification_prompt': result.get('state').clarification_prompt if result.get('state') else '',
            'validation_result': result.get('validation_result'),
            'sources': [result.get('state').search_source] if result.get('state') and result.get('state').search_source else [],
            'timestamp': datetime.now().isoformat(),
            'execution_time_ms': execution_time,
        })
        response._debug_headers = debug_headers(
            'success',
            query=query,
            status=str(result.get('validation_result') or result.get('state').current_agent if result.get('state') else 'unknown'),
            preview=(result.get('response', '')[:120] if result.get('response') else '')
        )
        return response, 200

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        response._debug_headers = debug_headers('error', status='unhandled-exception', preview=str(e))
        return response, 500


@app.route('/', methods=['GET'])
@app.route('/api/research', methods=['GET'])
def health_check():
    """Simple health check so the function responds with JSON."""
    response = jsonify({
        'success': True,
        'message': 'Business Research API is running',
    })
    response._debug_headers = debug_headers('health')
    return response
