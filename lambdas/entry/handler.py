import json
import boto3
import uuid
import os
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
stepfunctions = boto3.client("stepfunctions")

TABLE_NAME = os.environ["STORIES_TABLE"]
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def validate_input(body):
    """Validate card selections from request body."""
    required_fields = ["hero", "theme", "challenge", "strength"]
    
    valid_options = {
        "hero": ["boy", "girl"],
        "theme": ["space", "under_the_sea", "medieval_fantasy", "dinosaurs"],
        "challenge": ["asteroid", "wizard_witch", "dragon", "volcano"],
        "strength": ["super_strong", "friendship", "super_smart", "super_speed"],
    }
    
    for field in required_fields:
        if field not in body:
            raise ValueError(f"Missing required field: {field}")
        if body[field] not in valid_options[field]:
            raise ValueError(f"Invalid value for {field}: {body[field]}. Must be one of {valid_options[field]}")


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        validate_input(body)
        
        story_id = str(uuid.uuid4())
        
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(
            Item={
                "story_id": story_id,
                "hero": body["hero"],
                "theme": body["theme"],
                "challenge": body["challenge"],
                "strength": body["strength"],
                "status": "PROCESSING",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl": int(datetime.now(timezone.utc).timestamp()) + (30 * 24 * 60 * 60),
            }
        )
        
        stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=story_id,
            input=json.dumps({
                "story_id": story_id,
                "hero": body["hero"],
                "theme": body["theme"],
                "challenge": body["challenge"],
                "strength": body["strength"],
            }),
        )
        
        return {
            "statusCode": 202,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "story_id": story_id,
                "status": "PROCESSING",
                "message": "Story generation started",
            }),
        }

    except ValueError as e:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": str(e)}),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "Internal server error"}),
        }
