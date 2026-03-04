"""
Bedrock Chat Lambda

Accepts a natural-language NFL question, uses Claude 3 Haiku (via Bedrock)
to extract the structured game parameters, calls XGBoostPredictionLambda
for the model output, then asks Claude to format a clean response.

Flow:
  1. User message in → Claude tool-use call → extract teams / spread
  2. Invoke XGBoostPredictionLambda with extracted params
  3. Claude formats prediction result → natural-language response out
"""

import json
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
)
XGBOOST_LAMBDA_NAME = os.environ.get(
    "XGBOOST_LAMBDA_NAME", "XGBoostPredictionLambda"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)

# ---------------------------------------------------------------------------
# Tool schema Claude uses to extract game params from natural language
# ---------------------------------------------------------------------------

EXTRACT_TOOL = {
    "name": "predict_spread",
    "description": (
        "Extract NFL game parameters from the user's message and run a "
        "spread prediction. Call this whenever the user asks about an NFL "
        "game spread, who covers, or who wins against the spread."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "home_team": {
                "type": "string",
                "description": (
                    "3-letter NFL team abbreviation for the HOME team "
                    "(the team playing at their stadium). "
                    "Examples: BAL, BUF, KC, SF, DAL, GB, PHI, NE"
                ),
            },
            "away_team": {
                "type": "string",
                "description": (
                    "3-letter NFL team abbreviation for the AWAY team "
                    "(the team travelling). "
                    "In 'GB @ PIT', GB is away and PIT is home."
                ),
            },
            "spread_line": {
                "type": "number",
                "description": (
                    "The point spread from the HOME TEAM's perspective. "
                    "If home team is favored by 3, spread_line = -3. "
                    "If home team is a 3-point underdog, spread_line = 3."
                ),
            },
            "div_game": {
                "type": "boolean",
                "description": "True if both teams are in the same NFL division.",
            },
            "season": {
                "type": "integer",
                "description": "NFL season year (e.g. 2025). Default to 2025 if not specified.",
            },
        },
        "required": ["home_team", "away_team", "spread_line"],
    },
}

SYSTEM_PROMPT = """You are an expert NFL betting analyst assistant.

Your job is to answer questions about NFL game spread predictions using a machine learning model.

When a user asks about an NFL game (who covers, who wins ATS, spread predictions), 
call the predict_spread tool with the extracted parameters.

NFL team abbreviations reference:
AFC East: BUF, MIA, NE, NYJ
AFC North: BAL, CIN, CLE, PIT
AFC South: HOU, IND, JAX, TEN
AFC West: DEN, KC, LV, LAC
NFC East: DAL, NYG, PHI, WAS
NFC North: CHI, DET, GB, MIN
NFC South: ATL, CAR, NO, TB
NFC West: ARI, LAR, SEA, SF

Spread convention: "Team A -3 vs Team B" means Team A is favored by 3 points.
"@ symbol" means visiting team. In "GB @ PIT", GB is the away team, PIT is home.

After getting prediction results, explain them clearly:
- What the model predicts (margin)
- Which side covers and why
- Confidence level based on point difference from the spread
- Key context (division game, home advantage, etc.)

Be concise, confident, and use betting terminology naturally."""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _invoke_xgboost(params: dict) -> dict:
    """Call XGBoostPredictionLambda and return its parsed body."""
    logger.info(f"Invoking {XGBOOST_LAMBDA_NAME} with: {params}")
    response = lambda_client.invoke(
        FunctionName=XGBOOST_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(params),
    )
    raw = json.loads(response["Payload"].read())

    # Lambda returns {"statusCode": 200, "body": "{...json string...}"}
    if "body" in raw:
        return json.loads(raw["body"]) if isinstance(raw["body"], str) else raw["body"]
    return raw


def _call_bedrock(messages: list, tools: list | None = None) -> dict:
    """Single call to Bedrock Claude 3 Haiku. Returns the raw response body."""
    payload: dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())


def _format_prediction_for_claude(prediction: dict, user_message: str) -> str:
    """Ask Claude to turn raw prediction JSON into a natural language answer."""
    home = prediction.get("home_team", "?")
    away = prediction.get("away_team", "?")
    spread = prediction.get("spread_line", 0)
    margin = prediction.get("predicted_margin", 0)
    pick_team = prediction.get("pick_team", "?")
    confidence = prediction.get("confidence_pts", 0)
    model_pick = prediction.get("model_pick", "?")

    summary = (
        f"ML model prediction for {away} @ {home} (spread: {spread}):\n"
        f"  Predicted margin (home - away): {margin:.1f} points\n"
        f"  Model pick: {pick_team} covers ({model_pick} side)\n"
        f"  Confidence: {confidence:.1f} points off the spread\n"
    )

    messages = [
        {"role": "user", "content": user_message},
        {
            "role": "assistant",
            "content": (
                "I ran the ML model. Here are the raw results:\n\n"
                + summary
                + "\nLet me explain this clearly."
            ),
        },
        {
            "role": "user",
            "content": "Great, please give me a clear betting analysis based on those results.",
        },
    ]

    resp = _call_bedrock(messages)
    for block in resp.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return summary


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    Input (API Gateway or direct):
    {
        "message": "Who covers GB @ PIT with Packers -2.5?",
        "session_id": "optional"
    }

    Output:
    {
        "response": "Based on the ML model...",
        "prediction": { ...raw prediction data... }
    }
    """
    try:
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event

        user_message = body.get("message", "").strip()
        if not user_message:
            return {
                "statusCode": 400,
                "body": json.dumps({"success": False, "error": "message field is required"}),
            }

        logger.info(f"User message: {user_message}")

        # Step 1: Ask Claude to extract game params using tool use
        messages = [{"role": "user", "content": user_message}]
        first_response = _call_bedrock(messages, tools=[EXTRACT_TOOL])

        logger.info(f"Claude stop_reason: {first_response.get('stop_reason')}")

        prediction_data = None
        natural_language_response = None

        if first_response.get("stop_reason") == "tool_use":
            # Claude wants to call predict_spread
            tool_use_block = next(
                (b for b in first_response["content"] if b.get("type") == "tool_use"),
                None,
            )

            if tool_use_block:
                tool_input = tool_use_block["input"]
                logger.info(f"Claude extracted params: {tool_input}")

                # Step 2: Run the XGBoost prediction
                prediction_data = _invoke_xgboost(tool_input)

                if prediction_data.get("success"):
                    # Step 3: Format via Claude
                    natural_language_response = _format_prediction_for_claude(
                        prediction_data, user_message
                    )
                else:
                    natural_language_response = (
                        f"I extracted the game details but the prediction model returned an error: "
                        f"{prediction_data.get('error', 'unknown error')}. "
                        f"Please check that team abbreviations are correct and try again."
                    )
            else:
                natural_language_response = "I couldn't identify the game details. Please specify home team, away team, and spread (e.g. 'Who covers GB @ PIT with GB -2.5?')"

        else:
            # Claude responded with text (no game detected, or general question)
            for block in first_response.get("content", []):
                if block.get("type") == "text":
                    natural_language_response = block["text"]
                    break
            if not natural_language_response:
                natural_language_response = "I couldn't generate a response. Please try again."

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "success": True,
                "response": natural_language_response,
                "prediction": prediction_data,
            }),
        }

    except Exception as e:
        logger.error(f"BedrockChatLambda error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"success": False, "error": str(e)}),
        }
