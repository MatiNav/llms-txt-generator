from dataclasses import dataclass

from aws_cdk import aws_route53 as route53
from constructs import Construct


@dataclass(frozen=True)
class DomainNames:
    root_domain_name: str
    frontend_domain_name: str
    api_domain_name: str


class DomainService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        root_domain_name: str,
        frontend_subdomain_name: str,
        api_subdomain_name: str,
    ) -> None:
        super().__init__(scope, construct_id)

        self.hosted_zone = route53.HostedZone.from_lookup(
            self,
            "RootHostedZone",
            domain_name=root_domain_name,
        )
        self.domain_names = DomainNames(
            root_domain_name=root_domain_name,
            frontend_domain_name=f"{frontend_subdomain_name}.{root_domain_name}",
            api_domain_name=f"{api_subdomain_name}.{root_domain_name}",
        )
