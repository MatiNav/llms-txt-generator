from aws_cdk import aws_route53 as route53
from aws_cdk import custom_resources as custom_resources
from constructs import Construct


class AppRunnerDomainService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        hosted_zone: route53.IHostedZone,
        app_runner_service_arn: str,
        api_domain_name: str,
    ) -> None:
        super().__init__(scope, construct_id)

        # WORKAROUND:
        # App Runner can return multiple certificate validation CNAMEs.
        # We currently create two fixed records (indexes 0 and 1) to unblock.
        # Long-term solution would be replace this with a dynamic Lambda custom resource that
        # iterates through all returned CertificateValidationRecords.

        associate_domain_resource = custom_resources.AwsCustomResource(
            self,
            "AssociateCustomDomain",
            on_create=custom_resources.AwsSdkCall(
                service="AppRunner",
                action="associateCustomDomain",
                parameters={
                    "ServiceArn": app_runner_service_arn,
                    "DomainName": api_domain_name,
                    "EnableWWWSubdomain": False,
                },
                physical_resource_id=custom_resources.PhysicalResourceId.of(
                    f"{api_domain_name}-association"
                ),
            ),
            on_delete=custom_resources.AwsSdkCall(
                service="AppRunner",
                action="disassociateCustomDomain",
                parameters={
                    "ServiceArn": app_runner_service_arn,
                    "DomainName": api_domain_name,
                },
            ),
            policy=custom_resources.AwsCustomResourcePolicy.from_sdk_calls(
                resources=custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )

        describe_domain_resource = custom_resources.AwsCustomResource(
            self,
            "DescribeCustomDomain",
            on_create=custom_resources.AwsSdkCall(
                service="AppRunner",
                action="describeCustomDomains",
                parameters={
                    "ServiceArn": app_runner_service_arn,
                },
                physical_resource_id=custom_resources.PhysicalResourceId.of(
                    f"{api_domain_name}-describe"
                ),
            ),
            on_update=custom_resources.AwsSdkCall(
                service="AppRunner",
                action="describeCustomDomains",
                parameters={
                    "ServiceArn": app_runner_service_arn,
                },
                physical_resource_id=custom_resources.PhysicalResourceId.of(
                    f"{api_domain_name}-describe"
                ),
            ),
            policy=custom_resources.AwsCustomResourcePolicy.from_sdk_calls(
                resources=custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )
        describe_domain_resource.node.add_dependency(associate_domain_resource)

        validation_record_name_first = describe_domain_resource.get_response_field(
            "CustomDomains.0.CertificateValidationRecords.0.Name"
        )
        validation_record_value_first = describe_domain_resource.get_response_field(
            "CustomDomains.0.CertificateValidationRecords.0.Value"
        )

        validation_record_first = route53.CfnRecordSet(
            self,
            "ApiDomainValidationRecordFirst",
            hosted_zone_id=hosted_zone.hosted_zone_id,
            name=validation_record_name_first,
            type="CNAME",
            ttl="300",
            resource_records=[validation_record_value_first],
        )

        validation_record_name_second = describe_domain_resource.get_response_field(
            "CustomDomains.0.CertificateValidationRecords.1.Name"
        )
        validation_record_value_second = describe_domain_resource.get_response_field(
            "CustomDomains.0.CertificateValidationRecords.1.Value"
        )

        validation_record_second = route53.CfnRecordSet(
            self,
            "ApiDomainValidationRecordSecond",
            hosted_zone_id=hosted_zone.hosted_zone_id,
            name=validation_record_name_second,
            type="CNAME",
            ttl="300",
            resource_records=[validation_record_value_second],
        )

        dns_target = describe_domain_resource.get_response_field("DNSTarget")
        api_domain_record = route53.CfnRecordSet(
            self,
            "ApiDomainRecord",
            hosted_zone_id=hosted_zone.hosted_zone_id,
            name=f"{api_domain_name}.",
            type="CNAME",
            ttl="300",
            resource_records=[dns_target],
        )
        api_domain_record.node.add_dependency(validation_record_first)
        api_domain_record.node.add_dependency(validation_record_second)
