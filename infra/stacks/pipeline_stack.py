import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_iam as iam,
)
from constructs import Construct


class PipelineStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, storage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Story Generation Lambda ──────────────────────────────

        self.story_generation_lambda = lambda_.Function(
            self, "StoryGenerationLambda",
            function_name="my-story-generation",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambdas/story_generation"),
            timeout=cdk.Duration.seconds(120),
            environment={
                "STORIES_TABLE": storage.stories_table.table_name,
                "HF_ENDPOINT_URL": "PLACEHOLDER",
            },
        )

        # ── Image Generation Lambda ──────────────────────────────

        self.image_generation_lambda = lambda_.Function(
            self, "ImageGenerationLambda",
            function_name="my-story-image-generation",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambdas/image_generation"),
            timeout=cdk.Duration.seconds(120),
            environment={
                "IMAGES_BUCKET": storage.images_bucket.bucket_name,
                "REPLICATE_API_TOKEN": "PLACEHOLDER",
            },
        )

        # ── PDF Assembly Lambda ──────────────────────────────────

        self.pdf_assembly_lambda = lambda_.Function(
            self, "PdfAssemblyLambda",
            function_name="my-story-pdf-assembly",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambdas/pdf_assembly"),
            timeout=cdk.Duration.seconds(120),
            environment={
                "PDFS_BUCKET": storage.pdfs_bucket.bucket_name,
                "IMAGES_BUCKET": storage.images_bucket.bucket_name,
            },
        )

        # ── Permissions ───────────────────────────────────────────

        storage.stories_table.grant_read_write_data(self.story_generation_lambda)
        storage.images_bucket.grant_write(self.image_generation_lambda)
        storage.pdfs_bucket.grant_write(self.pdf_assembly_lambda)
        storage.images_bucket.grant_read(self.pdf_assembly_lambda)
        storage.stories_table.grant_write_data(self.pdf_assembly_lambda)

        # ── Step Functions Tasks ──────────────────────────────────

        # Task 1: Generate story text
        generate_story_task = tasks.LambdaInvoke(
            self, "GenerateStory",
            lambda_function=self.story_generation_lambda,
            output_path="$.Payload",
        )

        # Task 2: Generate images (fan-out — map state)
        generate_images_task = tasks.LambdaInvoke(
            self, "GenerateImages",
            lambda_function=self.image_generation_lambda,
            output_path="$.Payload",
        )

        # Task 3: Assemble PDF
        assemble_pdf_task = tasks.LambdaInvoke(
            self, "AssemblePdf",
            lambda_function=self.pdf_assembly_lambda,
            output_path="$.Payload",
        )

        # ── Step Functions State Machine ──────────────────────────

        # Define the pipeline: story → images → pdf
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