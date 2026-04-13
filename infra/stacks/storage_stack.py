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

        # Stories table — stores story metadata
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