"""
Vercel Serverless Python Function
Exposes the Business Research Agent as an HTTP API
Handler for POST requests with research queries
"""

import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any

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

# Initialize the graph once (Vercel reuses containers)
_graph = None

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


def handler(request):
    """
    Main Vercel handler function
    Receives POST requests with research queries
    Returns JSON with research results
    """
    start_time = datetime.now()
    headers = create_cors_headers()
    
    try:
        # Handle CORS preflight
        if request.method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
            }
        
        # Only accept POST
        if request.method != 'POST':
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({'error': 'Method not allowed. Use POST.'})
            }
        
        # Parse request body
        try:
            if isinstance(request.body, str):
                body = json.loads(request.body) if request.body else {}
            else:
                body = request.body if request.body else {}
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid JSON in request body'})
            }
        
        # Extract and validate query
        query = body.get('query', '').strip() if body.get('query') else ''
        is_valid, error_msg = validate_query(query)
        
        if not is_valid:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': error_msg})
            }
        
        # Get or initialize graph
        graph = get_graph()
        
        if not graph:
            # Fallback: use search directly
            try:
                search_results = search_duckduckgo(query, max_results=5)
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({
                        'success': True,
                        'response': f"Search results for '{query}':\n\n{search_results}",
                        'confidence': 5,
                        'sources': ['DuckDuckGo (Fallback)'],
                        'timestamp': datetime.now().isoformat(),
                        'execution_time_ms': execution_time,
                    })
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({'error': f'System initialization failed: {str(e)}'})
                }
        
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
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'success': True,
                    'response': result.get('final_response', ''),
                    'confidence': float(result.get('confidence_score', 0)),
                    'clarification_needed': result.get('clarity_status') == 'needs_clarification',
                    'clarification_prompt': result.get('clarification_prompt', ''),
                    'timestamp': datetime.now().isoformat(),
                    'execution_time_ms': execution_time,
                })
            }
        
        except Exception as agent_error:
            print(f"Agent Error: {str(agent_error)}")
            
            # Fallback: Simple search
            try:
                search_results = search_duckduckgo(query, max_results=5)
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({
                        'success': True,
                        'response': f"Search results for '{query}':\n\n{search_results}\n\n(Note: Using fallback search mode)",
                        'confidence': 5,
                        'sources': ['DuckDuckGo (Fallback)'],
                        'timestamp': datetime.now().isoformat(),
                        'execution_time_ms': execution_time,
                    })
                }
            except Exception as search_error:
                raise Exception(f"Agent failed: {str(agent_error)}, Search failed: {str(search_error)}")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': str(e),
                'execution_time_ms': execution_time,
            })
        }
