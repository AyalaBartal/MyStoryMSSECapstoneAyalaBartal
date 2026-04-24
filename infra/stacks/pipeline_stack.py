import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class PipelineStack(cdk.Stack):
    """The worker Lambdas + Step Functions state machine + API-key secrets.

    Pipeline shape:
        story_generation  →  image_generation  →  pdf_assembly
        (Claude Haiku)       (DALL-E 3)            (ReportLab + S3 + DDB)

    Any worker failure flips the DDB record to FAILED via a shared
    Step Functions state, so retrieval can tell the user the story
    errored out (rather than polling forever on PROCESSING).
    """

    def __init__(self, scope: Construct, construct_id: str, storage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── API-key secrets (Secrets Manager) ────────────────────
        # CDK creates these with auto-generated random values. After
        # the first deploy, overwrite them with your real keys:
        #   AWS Console → Secrets Manager → my-story/anthropic-api-key
        #                                → Retrieve secret value
        #                                → Edit → Plaintext → paste key
        #   Then repeat for my-story/openai-api-key.
        # The Lambdas read the key at cold start via ANTHROPIC_SECRET_ARN
        # / OPENAI_SECRET_ARN; the actual key never lives in env or code.

        self.anthropic_secret = secretsmanager.Secret(
            self, "AnthropicApiKey",
            secret_name="my-story/anthropic-api-key",
            description=(
                "Anthropic API key for Claude Haiku (story_generation Lambda). "
                "Replace the auto-generated value with your sk-ant-api03-... "
                "key via the AWS Console."
            ),
        )

        self.openai_secret = secretsmanager.Secret(
            self, "OpenAIApiKey",
            secret_name="my-story/openai-api-key",
            description=(
                "OpenAI API key for DALL-E 3 (image_generation Lambda). "
                "Replace the auto-generated value with your sk-proj-... "
                "key via the AWS Console."
            ),
        )

        # ── Story Generation Lambda ──────────────────────────────

        self.story_generation_lambda = lambda_.Function(
            self, "StoryGenerationLambda",
            function_name="my-story-generation",
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda_packages/story_generation.zip"),
            timeout=cdk.Duration.seconds(30),
            memory_size=512,
            environment={
                "ANTHROPIC_SECRET_ARN": self.anthropic_secret.secret_arn,
            },
        )
        self.anthropic_secret.grant_read(self.story_generation_lambda)

        # ── Image Generation Lambda ──────────────────────────────

        self.image_generation_lambda = lambda_.Function(
            self, "ImageGenerationLambda",
            function_name="my-story-image-generation",
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda_packages/image_generation.zip"),
            # DALL-E 3 × 5 images can run 30–60 seconds total.
            timeout=cdk.Duration.seconds(300),
            memory_size=512,
            environment={
                "IMAGES_BUCKET": storage.images_bucket.bucket_name,
                "OPENAI_SECRET_ARN": self.openai_secret.secret_arn,
            },
        )
        self.openai_secret.grant_read(self.image_generation_lambda)
        storage.images_bucket.grant_write(self.image_generation_lambda)

        # ── PDF Assembly Lambda ──────────────────────────────────

        self.pdf_assembly_lambda = lambda_.Function(
            self, "PdfAssemblyLambda",
            function_name="my-story-pdf-assembly",
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("lambda_packages/pdf_assembly.zip"),
            timeout=cdk.Duration.seconds(120),
            # ReportLab holds 5 images + PDF buffer in memory.
            memory_size=1024,
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "IMAGES_BUCKET": storage.images_bucket.bucket_name,
                "PDFS_BUCKET": storage.pdfs_bucket.bucket_name,
            },
        )
        storage.images_bucket.grant_read(self.pdf_assembly_lambda)
        storage.pdfs_bucket.grant_write(self.pdf_assembly_lambda)
        storage.stories_table.grant_write_data(self.pdf_assembly_lambda)

        # ── Step Functions Tasks ──────────────────────────────────

        generate_story_task = tasks.LambdaInvoke(
            self, "GenerateStory",
            lambda_function=self.story_generation_lambda,
            output_path="$.Payload",
        )

        generate_images_task = tasks.LambdaInvoke(
            self, "GenerateImages",
            lambda_function=self.image_generation_lambda,
            output_path="$.Payload",
        )

        assemble_pdf_task = tasks.LambdaInvoke(
            self, "AssemblePdf",
            lambda_function=self.pdf_assembly_lambda,
            output_path="$.Payload",
        )

        # ── Failure handling ──────────────────────────────────────
        # Shared state: flip the story's DDB status to FAILED, then Fail.
        # Every worker task catches States.ALL → this state, so the user
        # polling via the retrieval Lambda sees FAILED instead of being
        # stuck on PROCESSING forever.
        #
        # result_path="$.error_info" on the catch preserves the original
        # event (so $.story_id is still addressable inside MarkFailed).

        mark_failed = tasks.DynamoUpdateItem(
            self, "MarkFailed",
            table=storage.stories_table,
            key={
                "story_id": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.story_id")
                ),
            },
            update_expression="SET #s = :failed",
            expression_attribute_names={"#s": "status"},
            expression_attribute_values={
                ":failed": tasks.DynamoAttributeValue.from_string("FAILED"),
            },
            result_path=sfn.JsonPath.DISCARD,
        ).next(sfn.Fail(self, "PipelineFailed"))

        for task in (
            generate_story_task,
            generate_images_task,
            assemble_pdf_task,
        ):
            task.add_catch(
                mark_failed,
                errors=["States.ALL"],
                result_path="$.error_info",
            )

        # ── Step Functions State Machine ──────────────────────────

        pipeline_definition = (
            generate_story_task
            .next(generate_images_task)
            .next(assemble_pdf_task)
        )

        self.state_machine = sfn.StateMachine(
            self, "StoryPipeline",
            state_machine_name="my-story-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(
                pipeline_definition
            ),
            timeout=cdk.Duration.minutes(10),
        )

        # ── Outputs ───────────────────────────────────────────────

        cdk.CfnOutput(self, "StateMachineArn",
            value=self.state_machine.state_machine_arn)
        cdk.CfnOutput(self, "AnthropicSecretArn",
            value=self.anthropic_secret.secret_arn)
        cdk.CfnOutput(self, "OpenAISecretArn",
            value=self.openai_secret.secret_arn)