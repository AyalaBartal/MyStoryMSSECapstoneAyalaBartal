import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
)
from constructs import Construct


class StorageStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── S3 Buckets ──────────────────────────────────────────

        # Frontend bucket — hosts the React app
        self.frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            bucket_name=f"my-story-frontend-{self.account}",
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # PDFs bucket — stores generated story PDFs
        self.pdfs_bucket = s3.Bucket(
            self, "PdfsBucket",
            bucket_name=f"my-story-pdfs-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=cdk.Duration.days(30)
                )
            ],
        )

        # Images bucket — stores generated story illustrations
        self.images_bucket = s3.Bucket(
            self, "ImagesBucket",
            bucket_name=f"my-story-images-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Card illustrations bucket — stores pre-generated card images
        self.cards_bucket = s3.Bucket(
            self, "CardsBucket",
            bucket_name=f"my-story-cards-{self.account}",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── DynamoDB Table ───────────────────────────────────────

        # Stories table — stores story metadata.
        #
        # Sprint 4 ownership model:
        # - parent_id   — Cognito sub for logged-in users; null for anonymous
        # - kid_id      — links the story to a kid profile; null until claimed
        # - claim_token — random UUID for anonymous stories so a parent can
        #                 retroactively claim them by signing in
        #
        # GSIs let us query "all stories for parent X" or "all stories for
        # kid Y" without scanning the whole table.

        self.stories_table = dynamodb.Table(
            self, "StoriesTable",
            table_name="my-story-stories",
            partition_key=dynamodb.Attribute(
                name="story_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # GSI: query stories by parent_id (logged-in user's library).
        # Sort by created_at so the library shows newest first.
        self.stories_table.add_global_secondary_index(
            index_name="parent_id-index",
            partition_key=dynamodb.Attribute(
                name="parent_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING,
            ),
        )

        # GSI: query stories by kid_id (per-kid library page).
        self.stories_table.add_global_secondary_index(
            index_name="kid_id-index",
            partition_key=dynamodb.Attribute(
                name="kid_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING,
            ),
        )

        # Kids table — stores kid profiles per parent.
        #
        # Composite key: parent owns multiple kids, queried as a group.
        #   PK = parent_id  (Cognito sub)
        #   SK = kid_id     (UUID)
        #
        # Attributes (added at write time, schemaless):
        #   name             — kid's first name (used as story hero name)
        #   birth_year       — for age calculation
        #   avatar_card_id   — references the cards bucket for the kid's avatar
        #   created_at

        self.kids_table = dynamodb.Table(
            self, "KidsTable",
            table_name="my-story-kids",
            partition_key=dynamodb.Attribute(
                name="parent_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="kid_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── Outputs ──────────────────────────────────────────────

        cdk.CfnOutput(self, "FrontendBucketName",
            value=self.frontend_bucket.bucket_name)
        cdk.CfnOutput(self, "FrontendUrl",
            value=self.frontend_bucket.bucket_website_url)
        cdk.CfnOutput(self, "PdfsBucketName",
            value=self.pdfs_bucket.bucket_name)
        cdk.CfnOutput(self, "ImagesBucketName",
            value=self.images_bucket.bucket_name)
        cdk.CfnOutput(self, "CardsBucketName",
            value=self.cards_bucket.bucket_name)
        cdk.CfnOutput(self, "StoriesTableName",
            value=self.stories_table.table_name)
        cdk.CfnOutput(self, "KidsTableName",
                      value=self.kids_table.table_name)