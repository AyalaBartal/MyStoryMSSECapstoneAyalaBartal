import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct


class ApiStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, storage, pipeline, auth, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Entry Lambda ─────────────────────────────────────────

        self.entry_lambda = lambda_.Function(
            self, "EntryLambda",
            function_name="my-story-entry",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset("lambda_packages/entry.zip"),
            timeout=cdk.Duration.seconds(30),
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "PDFS_BUCKET": storage.pdfs_bucket.bucket_name,
                "STATE_MACHINE_ARN": pipeline.state_machine.state_machine_arn,
                "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
                "COGNITO_APP_CLIENT_ID": auth.user_pool_client.user_pool_client_id,
            },
        )

        # ── Retrieval Lambda ──────────────────────────────────────

        self.retrieval_lambda = lambda_.Function(
            self, "RetrievalLambda",
            function_name="my-story-retrieval",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset("lambda_packages/retrieval.zip"),
            timeout=cdk.Duration.seconds(30),
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "PDFS_BUCKET": storage.pdfs_bucket.bucket_name,
                "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
                "COGNITO_APP_CLIENT_ID": auth.user_pool_client.user_pool_client_id,
            },
        )

        # ── Kids Lambda ──────────────────────────────────────────

        self.kids_lambda = lambda_.Function(
            self, "KidsLambda",
            function_name="my-story-kids",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset("lambda_packages/kids.zip"),
            timeout=cdk.Duration.seconds(30),
            environment={
                "KIDS_TABLE": storage.kids_table.table_name,
                "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
                "COGNITO_APP_CLIENT_ID": auth.user_pool_client.user_pool_client_id,
            },
        )

        # Read+write on the kids table only (not stories).
        storage.kids_table.grant_read_write_data(self.kids_lambda)

        # ── Claim Stories Lambda ─────────────────────────────────

        self.claim_stories_lambda = lambda_.Function(
            self, "ClaimStoriesLambda",
            function_name="my-story-claim-stories",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset("lambda_packages/claim_stories.zip"),
            timeout=cdk.Duration.seconds(30),
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
                "COGNITO_APP_CLIENT_ID": auth.user_pool_client.user_pool_client_id,
            },
        )

        # Update on stories table — sets parent_id, removes claim_token.
        storage.stories_table.grant_read_write_data(self.claim_stories_lambda)

        # ── Permissions ───────────────────────────────────────────

        # Entry Lambda can read/write DynamoDB
        storage.stories_table.grant_read_write_data(self.entry_lambda)

        # Entry Lambda can start Step Functions
        pipeline.state_machine.grant_start_execution(self.entry_lambda)

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

        # GET /my-stories[?kid_id=...] — authed parent library
        my_stories = self.api.root.add_resource("my-stories")
        my_stories.add_method(
            "GET",
            apigw.LambdaIntegration(self.retrieval_lambda),
        )

        # POST   /kids
        # GET    /kids
        kids = self.api.root.add_resource("kids")
        kids.add_method(
            "POST",
            apigw.LambdaIntegration(self.kids_lambda),
        )
        kids.add_method(
            "GET",
            apigw.LambdaIntegration(self.kids_lambda),
        )

        # DELETE /kids/{kid_id}
        kid_id_resource = kids.add_resource("{kid_id}")
        kid_id_resource.add_method(
            "DELETE",
            apigw.LambdaIntegration(self.kids_lambda),
        )

        # POST /claim-stories
        claim_stories = self.api.root.add_resource("claim-stories")
        claim_stories.add_method(
            "POST",
            apigw.LambdaIntegration(self.claim_stories_lambda),
        )

        # ── Outputs ───────────────────────────────────────────────

        cdk.CfnOutput(self, "ApiUrl",
            value=self.api.url)
        cdk.CfnOutput(self, "GenerateEndpoint",
            value=f"{self.api.url}generate")
        cdk.CfnOutput(self, "StoryEndpoint",
            value=f"{self.api.url}story/{{story_id}}")