import json
import os
from pathlib import Path

import boto3

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

TABLE_NAME = os.environ["STORIES_TABLE"]
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Load prompt template once at cold-start; reused on warm invocations.
_PROMPT_PATH = Path(__file__).parent / "prompt_template.txt"
PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

CARD_LABELS = {
    "hero": {"boy": "boy", "girl": "girl"},
    "theme": {
        "space": "outer space among the stars",
        "under_the_sea": "deep under the ocean",
        "medieval_fantasy": "a magical medieval kingdom",
        "dinosaurs": "a prehistoric land of dinosaurs",
    },
    "adventure": {
        "secret_map": "finding a mysterious secret map",
        "talking_animal": "meeting a magical talking animal",
        "time_machine": "discovering an ancient time machine",
        "magic_key": "finding a glowing magic key",
    },
}


def build_prompt(name, age, hero, theme, adventure):
    return PROMPT_TEMPLATE.format(
        name=name,
        age=age,
        hero=CARD_LABELS["hero"][hero],
        theme=CARD_LABELS["theme"][theme],
        adventure=CARD_LABELS["adventure"][adventure],
    )


def save_story_pages(story_id, pages):
    table = dynamodb.Table(TABLE_NAME)
    table.update_item(
        Key={"story_id": story_id},
        UpdateExpression="SET pages = :pages, #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":pages": pages,
            ":status": "IMAGES_PENDING",
        },
    )


def lambda_handler(event, context):
    story_id = event["story_id"]
    name = event["name"]
    hero = event["hero"]
    theme = event["theme"]
    adventure = event["adventure"]
    age = event["age"]

    user_prompt = build_prompt(name, age, hero, theme, adventure)

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": user_prompt}],
        }),
    )

    response_body = json.loads(response["body"].read())
    story_text = response_body["content"][0]["text"].strip()

    # Strip accidental markdown fences if the model adds them.
    if story_text.startswith("```"):
        story_text = story_text.split("```")[1]
        if story_text.startswith("json"):
            story_text = story_text[4:]
        story_text = story_text.strip()

    parsed = json.loads(story_text)
    pages = parsed["pages"]

    save_story_pages(story_id, pages)

    return {
        "story_id": story_id,
        "name": name,
        "hero": hero,
        "theme": theme,
        "adventure": adventure,
        "age": age,
        "pages": pages,
    }