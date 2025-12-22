"""
OpenAI-powered Chatbot for NFL Spread Predictions
Uses GPT-4 with function calling to provide conversational betting insights
"""
import os
import json
import requests
from typing import Dict, List, Optional
from openai import OpenAI


class NFLPredictionChatbot:
    """Conversational interface for NFL spread predictions"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000", openai_api_key: Optional[str] = None):
        """
        Initialize chatbot with OpenAI and prediction API
        
        Args:
            api_base_url: Base URL for the FastAPI prediction service
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.client = OpenAI(api_key=openai_api_key or os.getenv('OPENAI_API_KEY'))
        
        # Conversation history
        self.conversation_history = [
            {
                "role": "system",
                "content": """You are an expert NFL betting analyst chatbot. You help users make informed 
betting decisions by analyzing spread predictions using historical Against The Spread (ATS) data.

Your predictions are based on three weighted factors:
1. **Situational ATS (40%)**: How teams perform in similar spread ranges and home/away situations
2. **Overall ATS (30%)**: Historical cover rate across all games
3. **Home/Away Performance (30%)**: Win rates based on location

When users ask about a game, you should:
- Ask for missing information (teams, spread, location) in a natural way
- Call the get_spread_prediction function to get data-driven analysis
- Explain predictions clearly with confidence levels
- Provide betting recommendations when confidence is >55%
- Be conversational and friendly, but professional

Always format team names consistently (use abbreviations: GB, PIT, etc.).
When displaying predictions, show probabilities as percentages and explain the key factors."""
            }
        ]
        
        # Function definitions for OpenAI function calling
        self.functions = [
            {
                "name": "get_spread_prediction",
                "description": "Get AI prediction for which team will cover the spread in an NFL game",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "away_team": {
                            "type": "string",
                            "description": "Away team abbreviation (e.g., 'GB', 'PIT')"
                        },
                        "home_team": {
                            "type": "string",
                            "description": "Home team abbreviation (e.g., 'GB', 'PIT')"
                        },
                        "spread": {
                            "type": "number",
                            "description": "Point spread (negative = away favored, positive = home favored)"
                        }
                    },
                    "required": ["away_team", "home_team", "spread"]
                }
            },
            {
                "name": "get_nfl_teams",
                "description": "Get list of all NFL teams with their abbreviations",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    def chat(self, user_message: str) -> str:
        """
        Process user message and return chatbot response
        
        Args:
            user_message: User's question or statement
            
        Returns:
            Chatbot's response
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Call OpenAI with function calling
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=self.conversation_history,
            functions=self.functions,
            function_call="auto",
            temperature=0.7
        )
        
        message = response.choices[0].message
        
        # Check if function was called
        if message.function_call:
            # Execute the function
            function_name = message.function_call.name
            function_args = json.loads(message.function_call.arguments)
            
            if function_name == "get_spread_prediction":
                function_response = self._get_prediction(
                    away_team=function_args['away_team'],
                    home_team=function_args['home_team'],
                    spread=function_args['spread']
                )
            elif function_name == "get_nfl_teams":
                function_response = self._get_teams()
            else:
                function_response = {"error": "Unknown function"}
            
            # Add function call and response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": function_name,
                    "arguments": message.function_call.arguments
                }
            })
            
            self.conversation_history.append({
                "role": "function",
                "name": function_name,
                "content": json.dumps(function_response)
            })
            
            # Get final response from GPT
            second_response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=self.conversation_history,
                temperature=0.7
            )
            
            final_message = second_response.choices[0].message.content
        else:
            final_message = message.content
        
        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": final_message
        })
        
        return final_message
    
    def _get_prediction(self, away_team: str, home_team: str, spread: float) -> Dict:
        """Call the prediction API"""
        try:
            # Convert spread: if positive, home team favored; if negative, away team favored
            # API expects spread from team_a perspective
            response = requests.post(
                f"{self.api_base_url}/predict",
                json={
                    "team_a": away_team.upper(),
                    "team_b": home_team.upper(),
                    "spread": spread,
                    "team_a_home": False,
                    "seasons": [2024, 2025]
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get prediction: {str(e)}"
            }
    
    def _get_teams(self) -> Dict:
        """Get list of NFL teams"""
        try:
            response = requests.get(f"{self.api_base_url}/teams", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "error": f"Failed to get teams: {str(e)}"
            }
    
    def reset_conversation(self):
        """Clear conversation history"""
        self.conversation_history = self.conversation_history[:1]  # Keep system message


# Command-line interface for testing
if __name__ == "__main__":
    import sys
    
    print("🏈 NFL Spread Prediction Chatbot")
    print("=" * 50)
    print("Ask me about any NFL game and I'll predict who covers!\n")
    
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    # Initialize chatbot
    chatbot = NFLPredictionChatbot()
    
    print("Type 'quit' or 'exit' to end the conversation")
    print("Type 'reset' to start a new conversation\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit']:
                print("\n👋 Thanks for using NFL Prediction Chatbot!")
                break
            
            if user_input.lower() == 'reset':
                chatbot.reset_conversation()
                print("🔄 Conversation reset!\n")
                continue
            
            response = chatbot.chat(user_input)
            print(f"\n🤖 Bot: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

