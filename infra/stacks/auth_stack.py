import aws_cdk as cdk
from aws_cdk import (
    aws_cognito as cognito,
    RemovalPolicy,
)
from constructs import Construct


class AuthStack(cdk.Stack):
    """Cognito User Pool + App Client + hosted UI for parent authentication.

    Provides:
      - User Pool — stores parent accounts (email + password)
      - App Client — credential the React frontend uses to call Cognito
      - Hosted UI domain — AWS-hosted sign-in/sign-up screens

    Sprint 4 only handles parent accounts. Kid profiles live in DynamoDB
    (my-story-kids table) keyed by parent's Cognito sub.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── User Pool ────────────────────────────────────────────
        # Email + password for Sprint 4. Social providers (Google, Apple)
        # deferred to backlog. Email verification required so we know
        # the address is real before sign-in is allowed.

        self.user_pool = cognito.UserPool(
            self, "ParentUserPool",
            user_pool_name="my-story-parents",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # DESTROY for the capstone. For production we'd use RETAIN
            # so accidental stack deletion doesn't wipe user accounts.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── App Client ───────────────────────────────────────────
        # The credential the React frontend uses to call Cognito APIs.
        # generate_secret=False because this runs in the browser — anyone
        # can read the source, so a "secret" wouldn't actually be secret.

        self.user_pool_client = cognito.UserPoolClient(
            self, "WebAppClient",
            user_pool=self.user_pool,
            user_pool_client_name="my-story-web",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            prevent_user_existence_errors=True,
        )

        # ── Hosted UI domain ─────────────────────────────────────
        # AWS-hosted sign-in/sign-up screens. The domain prefix must be
        # globally unique within the Cognito region — we suffix with
        # the AWS account ID to avoid collisions.

        self.user_pool_domain = self.user_pool.add_domain(
            "HostedUIDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"my-story-{self.account}",
            ),
        )

        # ── Outputs ──────────────────────────────────────────────
        # The React app reads UserPoolId + UserPoolClientId at build time
        # (passed as Vite env vars). HostedUIBaseUrl is for manual sign-in
        # testing during Phase 1.

        cdk.CfnOutput(self, "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID — frontend needs this")

        cdk.CfnOutput(self, "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito App Client ID — frontend needs this")

        cdk.CfnOutput(self, "HostedUIDomain",
            value=self.user_pool_domain.domain_name,
            description="Cognito hosted UI domain prefix")

        cdk.CfnOutput(self, "HostedUIBaseUrl",
            value=f"https://my-story-{self.account}.auth.{self.region}.amazoncognito.com",
            description="Hosted UI base URL for manual testing")