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
    # Ensure environment variables are reloaded from OS
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    start_time = datetime.now()
    
    try:
        # Handle CORS preflight
        if request.method == 'OPTIONS':
            response = jsonify({'success': True, 'message': 'CORS preflight ok'})
            response._debug_headers = debug_headers('preflight')
            return response, 200
        
        # Only accept POST
        if request.method != 'POST':
            response = jsonify({'error': 'Method not allowed. Use POST.'})
            response._debug_headers = debug_headers('error', status='method-not-allowed')
            return response, 405
        
        # Parse request body
        try:
            body = request.get_json(silent=True) or {}
        except json.JSONDecodeError:
            response = jsonify({'error': 'Invalid JSON in request body'})
            response._debug_headers = debug_headers('error', status='invalid-json')
            return response, 400
        
        # Extract and validate query
        query = body.get('query', '').strip() if body.get('query') else ''
        is_valid, error_msg = validate_query(query)
        
        if not is_valid:
            response = jsonify({'error': error_msg})
            response._debug_headers = debug_headers('error', query=query, status=error_msg)
            return response, 400
        
        # Get or initialize graph
        graph = get_graph()
        
        # Check if model was actually initialized within the graph
        model_active = graph is not None and graph.model is not None
        
        if not model_active:
            # Fallback: use search directly
            try:
                # DEBUG: Log environment state
                env_keys = list(os.environ.keys())
                has_g_key = 'GOOGLE_API_KEY' in os.environ
                has_gem_key = 'GEMINI_API_KEY' in os.environ
                
                search_results = search_duckduckgo(query, max_results=5)
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Check environment variables
                g_key = os.environ.get('GOOGLE_API_KEY')
                gem_key = os.environ.get('GEMINI_API_KEY')
                
                # Mask keys for safety
                g_masked = f"{g_key[:4]}...{g_key[-4:]}" if g_key and len(g_key) > 8 else ("Found" if g_key else "Missing")
                gem_masked = f"{gem_key[:4]}...{gem_key[-4:]}" if gem_key and len(gem_key) > 8 else ("Found" if gem_key else "Missing")
                
                debug_info = f"\n\n[DEBUG ENGINE: AI=Offline, G_KEY={g_masked}, GEM_KEY={gem_masked}, CWD={os.getcwd()}]"
                
                return jsonify({
                    'success': True,
                    'response': f"Search results for '{query}':\n\n{search_results}\n\n(Note: Using fallback search mode){debug_info}",
                    'confidence': 5,
                    'sources': ['DuckDuckGo (Fallback)'],
                    'timestamp': datetime.now().isoformat(),
                    'execution_time_ms': execution_time,
                })
            except Exception as e:
                response = jsonify({'error': f'System initialization failed: {str(e)}'})
                response._debug_headers = debug_headers('error', query=query, status='graph-init-failed', preview=str(e))
                return response, 500
        
        # Run the research workflow
        try:
            initial_state = {
                "messages": [],
                "current_query": query,
                "clarity_status": "clear",
                "clarity_explanation": "",
                "clarification_prompt": "",
                "research_findings": "",
                "confidence_score": 0,
                "search_source": "",
                "research_attempts": 0,
                "validation_result": "insufficient",
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
                
                # Check environment variables
                g_key = os.environ.get('GOOGLE_API_KEY')
                gem_key = os.environ.get('GEMINI_API_KEY')
                g_masked = f"{g_key[:4]}...{g_key[-4:]}" if g_key and len(g_key) > 8 else ("Found" if g_key else "Missing")
                gem_masked = f"{gem_key[:4]}...{gem_key[-4:]}" if gem_key and len(gem_key) > 8 else ("Found" if gem_key else "Missing")
                
                debug_info = f"\n\n[DEBUG ENGINE: Agent Error, Msg={str(agent_error)[:50]}, G_KEY={g_masked}, GEM_KEY={gem_masked}]"
                
                return jsonify({
                    'success': True,
                    'response': f"Search results for '{query}':\n\n{search_results}\n\n(Note: Using fallback search mode){debug_info}",
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
        
        response = jsonify({
            'error': str(e),
            'execution_time_ms': execution_time,
        })
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
