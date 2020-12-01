# Copyright 2015-2019 Yelp Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import List
from typing import Mapping
from typing import Optional

import service_configuration_lib

from paasta_tools.deployment import BranchDictV2
from paasta_tools.deployment import load_v2_deployments_json
from paasta_tools.kubernetes_tools import sanitised_cr_name
from paasta_tools.long_running_service_tools import LongRunningServiceConfig
from paasta_tools.long_running_service_tools import LongRunningServiceConfigDict
from paasta_tools.util.deep_merge import deep_merge_dictionaries
from paasta_tools.utils import DEFAULT_SOA_DIR
from paasta_tools.utils import load_service_instance_config


class KafkaClusterDeploymentConfigDict(LongRunningServiceConfigDict, total=False):
    replicas: int


class KafkaClusterDeploymentConfig(LongRunningServiceConfig):
    config_dict: KafkaClusterDeploymentConfigDict

    config_filename_prefix = "kafkacluster"

    def __init__(
        self,
        service: str,
        cluster: str,
        instance: str,
        config_dict: KafkaClusterDeploymentConfigDict,
        branch_dict: Optional[BranchDictV2],
        soa_dir: str = DEFAULT_SOA_DIR,
    ) -> None:

        super().__init__(
            cluster=cluster,
            instance=instance,
            service=service,
            soa_dir=soa_dir,
            config_dict=config_dict,
            branch_dict=branch_dict,
        )

    def get_instances(self, with_limit: bool = True) -> int:
        return self.config_dict.get("replicas", 1)

    def validate(
        self,
        params: List[str] = [
            "cpus",
            "security",
            "dependencies_reference",
            "deploy_group",
        ],
    ) -> List[str]:
        # Use InstanceConfig to validate shared config keys like cpus and mem
        # TODO: add mem back to this list once we fix PAASTA-15582 and
        # move to using the same units as flink/marathon etc.
        error_msgs = super().validate(params=params)

        if error_msgs:
            name = self.get_instance()
            return [f"{name}: {msg}" for msg in error_msgs]
        else:
            return []


def load_kafkacluster_instance_config(
    service: str,
    instance: str,
    cluster: str,
    load_deployments: bool = True,
    soa_dir: str = DEFAULT_SOA_DIR,
) -> KafkaClusterDeploymentConfig:
    """Read a service instance's configuration for KafkaCluster.

    If a branch isn't specified for a config, the 'branch' key defaults to
    paasta-${cluster}.${instance}.

    :param service: The service name
    :param instance: The instance of the service to retrieve
    :param cluster: The cluster to read the configuration for
    :param load_deployments: A boolean indicating if the corresponding deployments.json for this service
                             should also be loaded
    :param soa_dir: The SOA configuration directory to read from
    :returns: A dictionary of whatever was in the config for the service instance"""
    general_config = service_configuration_lib.read_service_configuration(
        service, soa_dir=soa_dir
    )
    instance_config = load_service_instance_config(
        service, instance, "kafkacluster", cluster, soa_dir=soa_dir
    )
    general_config = deep_merge_dictionaries(
        overrides=instance_config, defaults=general_config
    )

    branch_dict: Optional[BranchDictV2] = None
    if load_deployments:
        deployments_json = load_v2_deployments_json(service, soa_dir=soa_dir)
        temp_instance_config = KafkaClusterDeploymentConfig(
            service=service,
            cluster=cluster,
            instance=instance,
            config_dict=general_config,
            branch_dict=None,
            soa_dir=soa_dir,
        )
        branch = temp_instance_config.get_branch()
        deploy_group = temp_instance_config.get_deploy_group()
        branch_dict = deployments_json.get_branch_dict(service, branch, deploy_group)

    return KafkaClusterDeploymentConfig(
        service=service,
        cluster=cluster,
        instance=instance,
        config_dict=general_config,
        branch_dict=branch_dict,
        soa_dir=soa_dir,
    )


# TODO: read this from CRD in service configs
def cr_id(service: str, instance: str) -> Mapping[str, str]:
    return dict(
        group="yelp.com",
        version="v1alpha1",
        namespace="paasta-kafkaclusters",
        plural="kafkaclusters",
        name=sanitised_cr_name(service, instance),
    )
