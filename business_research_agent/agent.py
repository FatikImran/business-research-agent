"""
Multi-Agent Research Assistant using LangGraph
Built for Synapse AI Solutions

This module implements a sophisticated multi-agent research system that assists users
in collecting data about businesses. The system uses LangGraph to coordinate four
specialized agents: Clarity, Research, Validator, and Synthesis.

Agent Flow:
1. Clarity Agent: Evaluates query clarity and ambiguity
2. Research Agent: Searches for company data via DuckDuckGo (free, no API key needed)
3. Validator Agent: Assesses research quality and completeness
4. Synthesis Agent: Generates coherent summaries based on findings

This version uses:
- Google Gemini API (free tier) for LLM
- DuckDuckGo Search (completely free, no API key) for research
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum

from dotenv import load_dotenv

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDGS_AVAILABLE = True
    except ImportError:
        DDGS_AVAILABLE = False

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END, START
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Search multiple .env locations
load_dotenv() # Root
load_dotenv(os.path.join(os.path.dirname(__file__), '.env')) # /business_research_agent/.env
load_dotenv(os.path.join(os.getcwd(), 'business_research_agent', '.env')) # Absolute from cwd


class ClarityStatus(str, Enum):
    """Status of query clarity evaluation."""
    CLEAR = "clear"
    NEEDS_CLARIFICATION = "needs_clarification"


class ValidationResult(str, Enum):
    """Result of validation check."""
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class AgentState(BaseModel):
    """
    Comprehensive state schema for the multi-agent system.
    """
    messages: List[BaseMessage] = Field(
        default_factory=list,
        description="Conversation history with all messages"
    )
    
    current_query: str = Field(
        default="",
        description="The current user query being processed"
    )
    
    clarity_status: ClarityStatus = Field(
        default=ClarityStatus.CLEAR,
        description="Whether query is clear or needs clarification"
    )
    clarity_explanation: str = Field(
        default="",
        description="Explanation from clarity agent"
    )
    clarification_prompt: str = Field(
        default="",
        description="Prompt for user clarification if needed"
    )
    
    research_findings: str = Field(
        default="",
        description="Research findings from search tools"
    )
    confidence_score: float = Field(
        default=0.0,
        description="Confidence score of research (0-10)"
    )
    search_source: str = Field(
        default="",
        description="Source of search results"
    )
    research_attempts: int = Field(
        default=0,
        description="Number of research attempts made"
    )
    
    validation_result: ValidationResult = Field(
        default=ValidationResult.INSUFFICIENT,
        description="Whether validation passed or failed"
    )
    validation_notes: str = Field(
        default="",
        description="Notes from validator agent"
    )
    
    final_response: str = Field(
        default="",
        description="Final synthesized response for user"
    )
    
    conversation_context: str = Field(
        default="",
        description="Extracted context from conversation history"
    )
    
    current_agent: str = Field(
        default="clarity",
        description="Currently executing agent"
    )
    max_research_attempts: int = Field(
        default=3,
        description="Maximum number of research attempts allowed"
    )
    
    class Config:
        use_enum_values = False


def get_gemini_model():
    """
    Initialize Google Gemini model with safe API key handling.
    API key should be in GOOGLE_API_KEY environment variable.
    """
    if not GENAI_AVAILABLE:
        logger.warning("google-generativeai not installed")
        return None
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    
    # DEBUG: Log masked key information
    if api_key:
        logger.info(f"API Key found (length: {len(api_key)}, starts with: {api_key[:4]}...)")
    else:
        logger.warning("Neither GOOGLE_API_KEY nor GEMINI_API_KEY found in environment variables")
        return None
    
    try:
        genai.configure(api_key=api_key)
        # Reverted to gemini-2.5-flash as per user request
        model = genai.GenerativeModel('gemini-2.5-flash')
        # Test model availability with a lightweight request
        # model.get_model() # This verifies the model exists in the project
        logger.info("✓ Google Gemini API initialized successfully")
        return model
    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize Gemini API ({type(e).__name__}): {e}")
        return None
        logger.error(f"Failed to initialize Gemini API: {e}")
        return None


def extract_research_subject(query: str) -> str:
    """Extract the most likely company or topic from a natural-language research query."""
    if not query:
        return ""

    cleaned_query = re.sub(r"[\s\t\n\r]+", " ", query).strip().strip(".?!,")

    extraction_patterns = [
        r"(?:market overview of|overview of|company profile of|financial overview of|research|analyze|analyse|tell me about|learn about|look into|find out about)\s+(.+)$",
        r"(?:about|of|for|on|regarding)\s+(.+)$",
    ]

    for pattern in extraction_patterns:
        match = re.search(pattern, cleaned_query, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().strip(".?!,")
            if candidate:
                return candidate

    leading_noise = re.sub(
        r"^(?:please\s+)?(?:give me|tell me|research|analyze|analyse|summarize|summarise|show me|what is|what are|find|look up|provide)\s+",
        "",
        cleaned_query,
        flags=re.IGNORECASE,
    )
    leading_noise = re.sub(r"^(?:a|an|the)\s+", "", leading_noise, flags=re.IGNORECASE)

    if leading_noise:
        return leading_noise.strip().strip(".?!,")

    return cleaned_query


def search_duckduckgo(query: str, max_results: int = 5) -> str:
    """
    Perform a search using DuckDuckGo (completely free, no API key).
    """
    if not DDGS_AVAILABLE:
        logger.warning("duckduckgo_search not installed")
        return "DuckDuckGo search is unavailable in this environment."
    
    try:
        ddgs = DDGS()
        subject = extract_research_subject(query)
        
        # More diverse search variants to increase chance of results
        search_variants = [
            f"{subject} company information news financials",
            subject,
            f"what is {subject} company",
            f"{subject} official website",
            f"latest news about {subject}"
        ]

        logger.info(f"DuckDuckGo normalized subject: {subject}")

        for search_query in search_variants:
            if not search_query.strip():
                continue

            try:
                # Use text() with region="wt-wt" (global) and try/except for specific queries
                results = list(ddgs.text(search_query, max_results=max_results, region="wt-wt"))
            except Exception as search_error:
                logger.warning(f"DuckDuckGo variant failed for '{search_query}': {search_error}")
                results = []

            if results:
                formatted_results = f"Search query: {search_query}\n\nSearch Results:\n\n"
                for i, result in enumerate(results, 1):
                    formatted_results += f"{i}. {result.get('title', 'No title')}\n"
                    formatted_results += f"   {result.get('body', 'No description')}\n"
                    formatted_results += f"   Source: {result.get('href', 'No URL')}\n\n"

                return formatted_results

        return (
            f"No search results were found for '{subject}'. "
            "Please ensure the company name is spelled correctly or try using a more specific name."
        )
    
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return f"DuckDuckGo search error: {str(e)}"


class ClarityAgent:
    """Agent responsible for evaluating query clarity and specificity."""
    
    def __init__(self, model):
        self.model = model
    
    def evaluate_clarity(self, query: str, context: str = "") -> Dict[str, Any]:
        """Evaluate the clarity and specificity of a user query."""
        
        if not query or not query.strip():
            return {
                "clarity_status": ClarityStatus.NEEDS_CLARIFICATION,
                "explanation": "Empty query provided",
                "clarification_prompt": "Please provide a company name or research query."
            }
        
        if not self.model:
            # Fallback: Simple keyword-based clarity check
            keywords = ["company", "organization", "business", "firm", "corporation", "inc", "ltd", "llc"]
            has_company_ref = any(kw in query.lower() for kw in keywords) or len(query.split()) > 2
            
            if has_company_ref and len(query.strip()) > 10:
                return {
                    "clarity_status": ClarityStatus.CLEAR,
                    "explanation": "Query contains company reference and is specific enough",
                    "clarification_prompt": ""
                }
            else:
                return {
                    "clarity_status": ClarityStatus.NEEDS_CLARIFICATION,
                    "explanation": "Query is too vague or missing company name",
                    "clarification_prompt": "Which specific company would you like to research? Please provide the company name."
                }
        
        system_prompt = """You are a clarity evaluator for a business research assistant.

Your task is to determine if a user's query is:
1. CLEAR: Contains a specific company name and clear research intent
2. NEEDS_CLARIFICATION: Is ambiguous, vague, or missing company information

Respond ONLY with valid JSON (no markdown, no code blocks):
{
    "clarity_status": "clear" or "needs_clarification",
    "explanation": "Why is it clear or unclear?",
    "clarification_prompt": "If unclear, what should you ask the user?"
}"""
        
        user_message = f"Query: {query}\nContext: {context}" if context else f"Query: {query}"
        
        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n{user_message}",
                safety_settings={
                    HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            
            response_text = response.text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "clarity_status": ClarityStatus(result.get("clarity_status", "clear")),
                    "explanation": result.get("explanation", ""),
                    "clarification_prompt": result.get("clarification_prompt", "")
                }
        except Exception as e:
            logger.error(f"Error in clarity evaluation: {e}")
        
        return {
            "clarity_status": ClarityStatus.CLEAR,
            "explanation": "Query processed (fallback mode)",
            "clarification_prompt": ""
        }


class ResearchAgent:
    """Agent responsible for researching company information using DuckDuckGo."""
    
    def __init__(self, model):
        self.model = model
    
    def research_company(self, company_name: str, user_context: str = "") -> Dict[str, Any]:
        """Research a company using DuckDuckGo search."""
        
        if not company_name or not company_name.strip():
            return {
                "research_findings": "",
                "confidence_score": 0,
                "source": "error"
            }
        
        try:
            search_subject = extract_research_subject(company_name)
            search_query = f"{search_subject} company information recent news financial"
            if user_context:
                search_query += f" {user_context}"
            
            logger.info(f"Searching DuckDuckGo for: {search_query}")
            
            search_results = search_duckduckgo(search_query, max_results=5)
            
            if not search_results or not search_results.strip():
                return {
                    "research_findings": f"No search results found for {search_subject}",
                    "confidence_score": 3,
                    "source": "duckduckgo"
                }
            
            if self.model:
                system_prompt = """You are a business research expert. Analyze the search results and extract key information about the company.

Provide a structured summary including:
1. Company Overview
2. Key Financial Information (if available)
3. Recent Developments
4. Executive Leadership
5. Market Position

Also provide a confidence score (0-10) based on the quality and relevance of the search results.

Respond ONLY with this format (no markdown):
FINDINGS:
[Your detailed findings here]

CONFIDENCE_SCORE: [0-10]"""
                
                response = self.model.generate_content(
                    f"{system_prompt}\n\nSearch results for {company_name}:\n\n{search_results}",
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                    }
                )
                
                response_text = response.text
                
                confidence_score = 7
                if "CONFIDENCE_SCORE:" in response_text:
                    try:
                        score_str = response_text.split("CONFIDENCE_SCORE:")[-1].strip().split()[0]
                        confidence_score = float(score_str)
                        confidence_score = max(0, min(10, confidence_score))
                    except:
                        pass
                
                findings = response_text.split("FINDINGS:")[-1] if "FINDINGS:" in response_text else response_text
                
                return {
                    "research_findings": findings.strip(),
                    "confidence_score": confidence_score,
                    "source": "duckduckgo"
                }
            else:
                return {
                    "research_findings": search_results,
                    "confidence_score": 6,
                    "source": "duckduckgo"
                }
        
        except Exception as e:
            logger.error(f"Error in research: {e}")
            return {
                "research_findings": f"Error researching {company_name}: {str(e)}",
                "confidence_score": 2,
                "source": "error"
            }


class ValidatorAgent:
    """Agent responsible for validating research quality and completeness."""
    
    def __init__(self, model):
        self.model = model
    
    def validate_research(
        self,
        research_findings: str,
        original_query: str,
        confidence_score: float
    ) -> Dict[str, Any]:
        """Validate research quality and completeness."""
        
        if not research_findings or confidence_score < 3:
            return {
                "validation_result": ValidationResult.INSUFFICIENT,
                "validation_notes": "Research findings are insufficient or low confidence"
            }
        
        if not self.model:
            if confidence_score >= 6 and len(research_findings) > 100:
                return {
                    "validation_result": ValidationResult.SUFFICIENT,
                    "validation_notes": "Research findings are adequate"
                }
            else:
                return {
                    "validation_result": ValidationResult.INSUFFICIENT,
                    "validation_notes": "Research findings need improvement"
                }
        
        system_prompt = """You are a research quality validator. Assess whether the research findings adequately address the user's query.

Criteria for SUFFICIENT:
- Contains specific, relevant information
- Addresses the main aspects of the query
- Has adequate detail for user decision-making

Criteria for INSUFFICIENT:
- Missing key information
- Too vague or generic
- Does not directly address query

Respond ONLY with valid JSON:
{
    "validation_result": "sufficient" or "insufficient",
    "validation_notes": "Why is it sufficient or insufficient?"
}"""
        
        user_message = f"Query: {original_query}\n\nResearch Findings:\n{research_findings}"
        
        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n{user_message}",
                safety_settings={
                    HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            
            response_text = response.text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "validation_result": ValidationResult(result.get("validation_result", "insufficient")),
                    "validation_notes": result.get("validation_notes", "")
                }
        except Exception as e:
            logger.error(f"Error in validation: {e}")
        
        return {
            "validation_result": ValidationResult.SUFFICIENT,
            "validation_notes": "Validation passed (fallback mode)"
        }


class SynthesisAgent:
    """Agent responsible for synthesizing research findings into coherent responses."""
    
    def __init__(self, model):
        self.model = model
    
    def synthesize(
        self,
        research_findings: str,
        original_query: str,
        conversation_history: List[BaseMessage]
    ) -> str:
        """Synthesize research findings into a coherent response."""
        
        if not research_findings:
            return "I was unable to gather sufficient research to answer your question. Please try again with more specific details."
        
        if not self.model:
            return f"Based on research:\n\n{research_findings}"
        
        conversation_context = ""
        if conversation_history:
            for msg in conversation_history[-2:]:
                if isinstance(msg, HumanMessage):
                    conversation_context += f"User: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    conversation_context += f"Assistant: {msg.content}\n"
        
        system_prompt = """You are a professional business research analyst. Your task is to synthesize research findings into a clear, well-structured response.

Guidelines:
1. Address the user's specific question
2. Organize information logically
3. Use clear, professional language
4. Include specific details and data points
5. Maintain context from the conversation
6. Highlight key insights
7. Note any limitations in the data"""
        
        user_message = f"""Original Query: {original_query}

Conversation Context:
{conversation_context if conversation_context else "First message in conversation"}

Research Findings to Synthesize:
{research_findings}

Please provide a professional, well-structured response addressing the user's query."""
        
        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n{user_message}",
                safety_settings={
                    HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            
            return response.text
        except Exception as e:
            logger.error(f"Error in synthesis: {e}")
            return f"Based on the research findings:\n\n{research_findings}"


class BusinessResearchGraph:
    """Main orchestrator for the multi-agent research system."""
    
    def __init__(self):
        self.model = get_gemini_model()
        if not self.model:
            logger.warning("⚠ Gemini API not available - using fallback mode")
            logger.info("To use Gemini AI: Set GOOGLE_API_KEY environment variable")
        
        self.clarity_agent = ClarityAgent(self.model)
        self.research_agent = ResearchAgent(self.model)
        self.validator_agent = ValidatorAgent(self.model)
        self.synthesis_agent = SynthesisAgent(self.model)
        
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        graph = StateGraph(AgentState)
        
        graph.add_node("clarity", self._clarity_node)
        graph.add_node("research", self._research_node)
        graph.add_node("validator", self._validator_node)
        graph.add_node("synthesis", self._synthesis_node)
        graph.add_node("clarification_interrupt", self._clarification_interrupt_node)
        
        graph.add_edge(START, "clarity")
        
        graph.add_conditional_edges(
            "clarity",
            self._route_from_clarity,
            {"clarification": "clarification_interrupt", "research": "research"}
        )
        
        graph.add_edge("clarification_interrupt", "clarity")
        
        graph.add_conditional_edges(
            "research",
            self._route_from_research,
            {"validator": "validator", "synthesis": "synthesis"}
        )
        
        graph.add_conditional_edges(
            "validator",
            self._route_from_validator,
            {"research": "research", "synthesis": "synthesis"}
        )
        
        graph.add_edge("synthesis", END)
        
        return graph.compile()
    
    def _clarity_node(self, state: AgentState) -> AgentState:
        logger.info(f"[Clarity Agent] Evaluating: {state.current_query}")
        
        result = self.clarity_agent.evaluate_clarity(
            query=state.current_query,
            context=state.conversation_context
        )
        
        state.clarity_status = result["clarity_status"]
        state.clarity_explanation = result["explanation"]
        state.clarification_prompt = result["clarification_prompt"]
        state.current_agent = "clarity"
        
        logger.info(f"[Clarity Agent] Status: {state.clarity_status.value}")
        
        return state
    
    def _research_node(self, state: AgentState) -> AgentState:
        state.research_attempts += 1
        logger.info(f"[Research Agent] Attempt {state.research_attempts}: Researching {state.current_query}")
        
        result = self.research_agent.research_company(
            company_name=state.current_query,
            user_context=state.conversation_context
        )
        
        state.research_findings = result["research_findings"]
        state.confidence_score = result["confidence_score"]
        state.search_source = result["source"]
        state.current_agent = "research"
        
        logger.info(f"[Research Agent] Confidence: {state.confidence_score}")
        
        return state
    
    def _validator_node(self, state: AgentState) -> AgentState:
        logger.info("[Validator Agent] Validating research quality")
        
        result = self.validator_agent.validate_research(
            research_findings=state.research_findings,
            original_query=state.current_query,
            confidence_score=state.confidence_score
        )
        
        state.validation_result = result["validation_result"]
        state.validation_notes = result["validation_notes"]
        state.current_agent = "validator"
        
        logger.info(f"[Validator Agent] Result: {state.validation_result.value}")
        
        return state
    
    def _synthesis_node(self, state: AgentState) -> AgentState:
        logger.info("[Synthesis Agent] Synthesizing findings")
        
        final_response = self.synthesis_agent.synthesize(
            research_findings=state.research_findings,
            original_query=state.current_query,
            conversation_history=state.messages
        )
        
        state.final_response = final_response
        state.current_agent = "synthesis"
        
        logger.info("[Synthesis Agent] Response generated")
        
        return state
    
    def _clarification_interrupt_node(self, state: AgentState) -> AgentState:
        logger.info("[Clarification] Prompting user for clarification")
        state.current_agent = "clarification_interrupt"
        return state
    
    def _route_from_clarity(self, state: AgentState) -> str:
        if state.clarity_status == ClarityStatus.NEEDS_CLARIFICATION:
            return "clarification"
        return "research"
    
    def _route_from_research(self, state: AgentState) -> str:
        if state.confidence_score >= 6:
            return "synthesis"
        return "validator"
    
    def _route_from_validator(self, state: AgentState) -> str:
        if state.validation_result == ValidationResult.SUFFICIENT:
            return "synthesis"
        elif state.research_attempts < state.max_research_attempts:
            return "research"
        else:
            return "synthesis"
    
    def process_query(self, user_input: str, state: Optional[AgentState] = None) -> Dict[str, Any]:
        """Process a user query through the multi-agent system."""
        
        if not user_input or not user_input.strip():
            return {
                "response": "Please provide a query.",
                "status": "error",
                "clarification_needed": False,
                "confidence_score": 0.0
            }
        
        if state is None:
            state = AgentState()
        
        state.messages.append(HumanMessage(content=user_input))
        state.current_query = user_input
        
        if len(state.messages) > 2:
            state.conversation_context = " ".join([
                m.content for m in state.messages[-4:-1]
                if isinstance(m, (HumanMessage, AIMessage))
            ])
        
        try:
            result_state = self.graph.invoke(state)
            
            if result_state.final_response:
                result_state.messages.append(AIMessage(content=result_state.final_response))
            elif result_state.clarification_prompt:
                result_state.messages.append(AIMessage(content=result_state.clarification_prompt))
            
            return {
                "response": result_state.final_response or result_state.clarification_prompt,
                "status": "success",
                "clarification_needed": result_state.clarity_status == ClarityStatus.NEEDS_CLARIFICATION,
                "confidence_score": result_state.confidence_score,
                "validation_result": result_state.validation_result.value if result_state.validation_result else None,
                "state": result_state
            }
        
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "response": "An error occurred while processing your query. Please try again.",
                "status": "error",
                "clarification_needed": False,
                "confidence_score": 0.0,
                "error": str(e)
            }


if __name__ == "__main__":
    print("Initializing Business Research Assistant...")
    assistant = BusinessResearchGraph()
    
    test_queries = [
        "Tell me about Apple Inc",
        "What about their recent developments?",
    ]
    
    state = None
    for query in test_queries:
        print(f"\nUser: {query}")
        result = assistant.process_query(query, state)
        
        print(f"Response: {result['response'][:200]}...")
        print(f"Status: {result['status']}")
        print(f"Confidence: {result['confidence_score']}")
        
        state = result.get('state')
