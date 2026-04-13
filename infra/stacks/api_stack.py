import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct


class ApiStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, storage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Entry Lambda ─────────────────────────────────────────

        self.entry_lambda = lambda_.Function(
            self, "EntryLambda",
            function_name="my-story-entry",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambdas/entry"),
            timeout=cdk.Duration.seconds(30),
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "PDFS_BUCKET": storage.pdfs_bucket.bucket_name,
            },
        )

        # ── Retrieval Lambda ──────────────────────────────────────

        self.retrieval_lambda = lambda_.Function(
            self, "RetrievalLambda",
            function_name="my-story-retrieval",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambdas/retrieval"),
            timeout=cdk.Duration.seconds(30),
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "PDFS_BUCKET": storage.pdfs_bucket.bucket_name,
            },
        )

        # ── Permissions ───────────────────────────────────────────

        # Entry Lambda can read/write DynamoDB
        storage.stories_table.grant_read_write_data(self.entry_lambda)

        # Retrieval Lambda can read DynamoDB and S3
        storage.stories_table.grant_read_data(self.retrieval_lambda)
        storage.pdfs_bucket.grant_read(self.retrieval_lambda)

        # ── API Gateway ───────────────────────────────────────────

        self.api = apigw.RestApi(
            self, "MyStoryApi",
            rest_api_name="my-story-api",
            description="My Story API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        # POST /generate
        generate = self.api.root.add_resource("generate")
        generate.add_method(
            "POST",
            apigw.LambdaIntegration(self.entry_lambda),
        )

        # GET /story/{story_id}
        story = self.api.root.add_resource("story")
        story_id = story.add_resource("{story_id}")
        story_id.add_method(
            "GET",
            apigw.LambdaIntegration(self.retrieval_lambda),
        )

        # ── Outputs ───────────────────────────────────────────────

        cdk.CfnOutput(self, "ApiUrl",
            value=self.api.url)
        cdk.CfnOutput(self, "GenerateEndpoint",
            value=f"{self.api.url}generate")
        cdk.CfnOutput(self, "StoryEndpoint",
            value=f"{self.api.url}story/{{story_id}}")