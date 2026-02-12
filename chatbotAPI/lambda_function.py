"""
Chatbot API Lambda Handler
User-facing chatbot interface that calls playerimpact and predictivedatamodel Lambdas
"""

import json
import os
import logging
import boto3
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Lambda client for invoking other Lambdas
lambda_client = boto3.client('lambda')


def lambda_handler(event, context):
    """
    AWS Lambda handler for chatbot API
    
    Event format (from API Gateway):
    {
        "action": "predict_spread",
        "team_a": "BAL",
        "team_b": "BUF",
        "spread_line": 2.5,
        "spread_favorite": "team_a",
        "season": 2024
    }
    
    Returns:
    {
        "prediction": {...},
        "player_impact": {...}
    }
    """
    
    try:
        # Parse event (handle API Gateway format)
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        action = body.get('action', 'predict_spread')
        
        logger.info(f"ChatbotAPI invoked: action={action}")
        
        if action == 'predict_spread':
            return handle_prediction(body)
        
        elif action == 'get_player_impact':
            return handle_player_impact(body)
        
        elif action == 'full_analysis':
            return handle_full_analysis(body)
        
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': f'Unknown action: {action}'
                })
            }
    
    except Exception as e:
        logger.error(f"ChatbotAPI error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def handle_prediction(body: Dict[str, Any]) -> Dict[str, Any]:
    """Call predictivedatamodel Lambda for spread prediction"""
    
    payload = {
        'team_a': body['team_a'],
        'team_b': body['team_b'],
        'spread_line': float(body['spread_line']),
        'spread_favorite': body.get('spread_favorite', 'team_a')
    }
    
    logger.info(f"Invoking predictivedatamodel Lambda: {payload}")
    
    try:
        response = lambda_client.invoke(
            FunctionName='predictivedatamodel',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        return result
    
    except Exception as e:
        logger.error(f"Error invoking predictivedatamodel: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Failed to get prediction: {str(e)}'
            })
        }


def handle_player_impact(body: Dict[str, Any]) -> Dict[str, Any]:
    """Call playerimpact Lambda for player impact calculation"""
    
    payload = {
        'team_a': body['team_a'],
        'team_b': body['team_b'],
        'season': body.get('season', 2024)
    }
    
    logger.info(f"Invoking playerimpact Lambda: {payload}")
    
    try:
        response = lambda_client.invoke(
            FunctionName='playerimpact',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        return result
    
    except Exception as e:
        logger.error(f"Error invoking playerimpact: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Failed to get player impact: {str(e)}'
            })
        }


def handle_full_analysis(body: Dict[str, Any]) -> Dict[str, Any]:
    """Get both spread prediction and player impact"""
    
    logger.info("Performing full analysis (prediction + player impact)")
    
    # Call both Lambdas in parallel
    prediction_result = handle_prediction(body)
    player_impact_result = handle_player_impact(body)
    
    # Combine results
    prediction_data = json.loads(prediction_result['body']) if 'body' in prediction_result else prediction_result
    player_impact_data = json.loads(player_impact_result['body']) if 'body' in player_impact_result else player_impact_result
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'prediction': prediction_data,
            'player_impact': player_impact_data,
            'matchup': {
                'team_a': body['team_a'],
                'team_b': body['team_b'],
                'spread_line': float(body['spread_line'])
            }
        })
    }


# For local testing
if __name__ == "__main__":
    test_event = {
        "action": "full_analysis",
        "team_a": "BAL",
        "team_b": "BUF",
        "spread_line": 2.5,
        "spread_favorite": "team_a",
        "season": 2024
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

