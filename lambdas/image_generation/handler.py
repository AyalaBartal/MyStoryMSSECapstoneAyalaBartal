import json


def lambda_handler(event, context):
    # TODO: Sprint 2 Task 23 — image generation implementation
    return {
        "story_id": event.get("story_id"),
        "image_urls": []
    }