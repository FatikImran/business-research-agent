"""
Interactive CLI for the Business Research Assistant

Provides a user-friendly interface for interacting with the multi-agent system,
with support for multi-turn conversations and follow-up questions.

Uses:
- Google Gemini API (free tier)
- DuckDuckGo Search (completely free, no API key)
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from agent import BusinessResearchGraph, AgentState

# Load environment variables
load_dotenv()


class ResearchAssistantCLI:
    """Interactive CLI interface for the business research assistant."""
    
    def __init__(self):
        print("\n" + "="*80)
        print("BUSINESS RESEARCH ASSISTANT - Multi-Agent System")
        print("Powered by LangGraph | Using Gemini AI + DuckDuckGo Search")
        print("="*80 + "\n")
        
        # Check for API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("⚠  WARNING: GOOGLE_API_KEY not found!")
            print("   Using fallback mode (limited functionality)")
            print("   To enable full features, set the GOOGLE_API_KEY environment variable")
            print("   (Completely free - get it at https://ai.google.dev/)\n")
        
        print("Initializing system...")
        self.graph = BusinessResearchGraph()
        self.conversation_state: Optional[AgentState] = None
        print("✓ System initialized successfully\n")
    
    def display_menu(self):
        """Display the main menu."""
        print("\nOptions:")
        print("  1. Ask a new question")
        print("  2. View conversation history")
        print("  3. Clear conversation")
        print("  4. Save conversation to file")
        print("  5. Exit")
        print()
    
    def display_response(self, result: dict):
        """Display the result of query processing."""
        print("\n" + "-"*80)
        
        if result.get('response'):
            print("Assistant Response:")
            print(result['response'])
        
        print("\n" + "-"*40)
        print("Processing Metadata:")
        print(f"  Status: {result.get('status', 'unknown')}")
        
        if result.get('confidence_score') is not None:
            print(f"  Confidence Score: {result.get('confidence_score'):.1f}/10")
        
        if result.get('validation_result'):
            print(f"  Validation Result: {result.get('validation_result')}")
        
        if result.get('clarification_needed'):
            print("  ⚠ Clarification needed from user")
        
        print("-"*80 + "\n")
    
    def get_user_input(self) -> str:
        """Get input from user."""
        try:
            return input("You: ").strip()
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            return "exit"
        except EOFError:
            return "exit"
    
    def view_history(self):
        """Display conversation history."""
        if not self.conversation_state or not self.conversation_state.messages:
            print("\nNo conversation history yet.\n")
            return
        
        print("\n" + "="*80)
        print("CONVERSATION HISTORY")
        print("="*80 + "\n")
        
        for i, msg in enumerate(self.conversation_state.messages, 1):
            if hasattr(msg, 'content'):
                sender = type(msg).__name__
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                print(f"{i}. [{sender}]: {content}")
        
        print("\n" + "="*80 + "\n")
    
    def clear_conversation(self):
        """Clear conversation history."""
        response = input("Clear conversation history? (yes/no): ").strip().lower()
        if response == 'yes':
            self.conversation_state = None
            print("✓ Conversation history cleared.\n")
        else:
            print("✗ Cancelled.\n")
    
    def save_conversation(self):
        """Save conversation to a file."""
        if not self.conversation_state or not self.conversation_state.messages:
            print("\nNo conversation to save.\n")
            return
        
        filename = f"conversation_{len(self.conversation_state.messages)}_turns.json"
        filepath = Path(filename)
        
        try:
            conversation_data = {
                "messages": [
                    {
                        "type": type(msg).__name__,
                        "content": msg.content
                    }
                    for msg in self.conversation_state.messages
                ],
                "total_turns": len(self.conversation_state.messages),
                "final_confidence": self.conversation_state.confidence_score,
                "final_validation": self.conversation_state.validation_result.value if self.conversation_state.validation_result else None
            }
            
            with open(filepath, 'w') as f:
                json.dump(conversation_data, f, indent=2)
            
            print(f"\n✓ Conversation saved to {filepath}\n")
        
        except Exception as e:
            print(f"\n✗ Error saving conversation: {e}\n")
    
    def run(self):
        """Run the interactive CLI."""
        print("Type 'menu' for options, 'exit' to quit, or ask your question.\n")
        
        while True:
            try:
                user_input = self.get_user_input()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("\nThank you for using Business Research Assistant. Goodbye!\n")
                    break
                
                if user_input.lower() == 'menu':
                    self.display_menu()
                    continue
                
                if user_input.lower() == 'history':
                    self.view_history()
                    continue
                
                if user_input.lower() == 'clear':
                    self.clear_conversation()
                    continue
                
                if user_input.lower() == 'save':
                    self.save_conversation()
                    continue
                
                print("\nProcessing your query...")
                result = self.graph.process_query(user_input, self.conversation_state)
                
                if result.get('state'):
                    self.conversation_state = result['state']
                
                self.display_response(result)
            
            except KeyboardInterrupt:
                print("\n\nExiting... Goodbye!\n")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}\n")
                print("Please try again or type 'exit' to quit.\n")


if __name__ == "__main__":
    cli = ResearchAssistantCLI()
    cli.run()
    
    def display_menu(self):
        """Display the main menu."""
        print("\nOptions:")
        print("  1. Ask a new question")
        print("  2. View conversation history")
        print("  3. Clear conversation")
        print("  4. Save conversation to file")
        print("  5. Exit")
        print()
    
    def display_response(self, result: dict):
        """Display the result of query processing."""
        print("\n" + "-"*80)
        
        # Main response
        if result.get('response'):
            print("Assistant Response:")
            print(result['response'])
        
        # Metadata
        print("\n" + "-"*40)
        print("Processing Metadata:")
        print(f"  Status: {result.get('status', 'unknown')}")
        
        if result.get('confidence_score') is not None:
            print(f"  Confidence Score: {result.get('confidence_score'):.1f}/10")
        
        if result.get('validation_result'):
            print(f"  Validation Result: {result.get('validation_result')}")
        
        if result.get('clarification_needed'):
            print("  ⚠ Clarification needed from user")
        
        print("-"*80 + "\n")
    
    def get_user_input(self) -> str:
        """Get input from user."""
        try:
            return input("You: ").strip()
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            return "exit"
        except EOFError:
            return "exit"
    
    def view_history(self):
        """Display conversation history."""
        if not self.conversation_state or not self.conversation_state.messages:
            print("\nNo conversation history yet.\n")
            return
        
        print("\n" + "="*80)
        print("CONVERSATION HISTORY")
        print("="*80 + "\n")
        
        for i, msg in enumerate(self.conversation_state.messages, 1):
            if hasattr(msg, 'content'):
                sender = type(msg).__name__
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                print(f"{i}. [{sender}]: {content}")
        
        print("\n" + "="*80 + "\n")
    
    def clear_conversation(self):
        """Clear conversation history."""
        response = input("Clear conversation history? (yes/no): ").strip().lower()
        if response == 'yes':
            self.conversation_state = None
            print("✓ Conversation history cleared.\n")
        else:
            print("✗ Cancelled.\n")
    
    def save_conversation(self):
        """Save conversation to a file."""
        if not self.conversation_state or not self.conversation_state.messages:
            print("\nNo conversation to save.\n")
            return
        
        filename = f"conversation_{len(self.conversation_state.messages)}_turns.json"
        filepath = Path(filename)
        
        try:
            # Prepare data
            conversation_data = {
                "messages": [
                    {
                        "type": type(msg).__name__,
                        "content": msg.content
                    }
                    for msg in self.conversation_state.messages
                ],
                "total_turns": len(self.conversation_state.messages),
                "final_confidence": self.conversation_state.confidence_score,
                "final_validation": self.conversation_state.validation_result.value if self.conversation_state.validation_result else None
            }
            
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(conversation_data, f, indent=2)
            
            print(f"\n✓ Conversation saved to {filepath}\n")
        
        except Exception as e:
            print(f"\n✗ Error saving conversation: {e}\n")
    
    def run(self):
        """Run the interactive CLI."""
        print("Type 'menu' for options, 'exit' to quit, or ask your question.\n")
        
        while True:
            try:
                user_input = self.get_user_input()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() == 'exit':
                    print("\nThank you for using Business Research Assistant. Goodbye!\n")
                    break
                
                if user_input.lower() == 'menu':
                    self.display_menu()
                    continue
                
                if user_input.lower() == 'history':
                    self.view_history()
                    continue
                
                if user_input.lower() == 'clear':
                    self.clear_conversation()
                    continue
                
                if user_input.lower() == 'save':
                    self.save_conversation()
                    continue
                
                # Process query
                print("\nProcessing your query...")
                result = self.graph.process_query(user_input, self.conversation_state)
                
                # Update state for next turn
                if result.get('state'):
                    self.conversation_state = result['state']
                
                # Display result
                self.display_response(result)
            
            except KeyboardInterrupt:
                print("\n\nExiting... Goodbye!\n")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}\n")
                print("Please try again or type 'exit' to quit.\n")


if __name__ == "__main__":
    cli = ResearchAssistantCLI()
    cli.run()
