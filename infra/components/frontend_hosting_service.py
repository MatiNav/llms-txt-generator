from pathlib import Path

from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk.aws_cloudfront_origins import S3BucketOrigin
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as route53_targets
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3_deployment
from constructs import Construct


class FrontendHostingService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        hosted_zone: route53.IHostedZone,
        frontend_domain_name: str,
    ) -> None:
        super().__init__(scope, construct_id)

        frontend_certificate = acm.Certificate(
            self,
            "FrontendCertificate",
            domain_name=frontend_domain_name,
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        frontend_distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=S3BucketOrigin.with_origin_access_control(frontend_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
            domain_names=[frontend_domain_name],
            certificate=frontend_certificate,
        )

        frontend_record_name = frontend_domain_name.removesuffix(
            f".{hosted_zone.zone_name}"
        )
        route53.ARecord(
            self,
            "FrontendAliasRecord",
            zone=hosted_zone,
            record_name=frontend_record_name,
            target=route53.RecordTarget.from_alias(
                route53_targets.CloudFrontTarget(frontend_distribution)
            ),
        )

        repository_root = Path(__file__).resolve().parents[2]
        frontend_dist_path = repository_root / "app" / "frontend" / "dist"
        s3_deployment.BucketDeployment(
            self,
            "FrontendDeployment",
            destination_bucket=frontend_bucket,
            sources=[s3_deployment.Source.asset(str(frontend_dist_path))],
            distribution=frontend_distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )

        CfnOutput(
            self,
            "FrontendPublicUrl",
            value=f"https://{frontend_domain_name}",
            description="Public frontend URL",
        )

        self.frontend_bucket = frontend_bucket
        self.frontend_distribution = frontend_distribution
        self.frontend_domain_name = frontend_domain_name
