from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
import os

class RpaOcrEcsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a VPC with public and private subnets
        vpc = ec2.Vpc(
            self, "RpaOcrVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="PrivateSubnet",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

        # Create an ECS cluster
        cluster = ecs.Cluster(
            self, "RpaOcrCluster",
            vpc=vpc,
            cluster_name="rpa-ocr-cluster"
        )

        # Create IAM role for ECS task
        task_role = iam.Role(
            self, "RpaOcrTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for RPA OCR ECS task"
        )

        # Add permissions for the application
        task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
        )
        task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
        )
        task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess")
        )

        # Create execution role for ECS task
        execution_role = iam.Role(
            self, "RpaOcrExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM execution role for RPA OCR ECS task"
        )
        execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
        )

        # Create CloudWatch log group
        log_group = logs.LogGroup(
            self, "RpaOcrLogGroup",
            log_group_name="/ecs/rpa-ocr",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create Fargate task definition
        task_definition = ecs.FargateTaskDefinition(
            self, "RpaOcrTaskDefinition",
            memory_limit_mib=2048,
            cpu=1024,
            task_role=task_role,
            execution_role=execution_role,
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.ARM64
            ),
        )

        # Container definition
        container = task_definition.add_container(
            "RpaOcrContainer",
            image=ecs.ContainerImage.from_asset("../"),  # Build from parent directory
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="rpa-ocr",
                log_group=log_group
            ),
            environment={
                "AWS_REGION": "us-west-2",
                "S3_BUCKET": "medical-ocr-495599739878",
                "DYNAMODB_TABLE_NAME": "medical-ocr-results",
                "DYNAMODB_IMAGES_TABLE_NAME": "medical-ocr-images",
                "FLASK_ENV": "production",
                "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0"
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:5006/ || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60)
            )
        )

        # Container port mapping
        container.add_port_mappings(
            ecs.PortMapping(
                container_port=5006,
                protocol=ecs.Protocol.TCP
            )
        )

        # Create Application Load Balanced Fargate Service
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "RpaOcrFargateService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            assign_public_ip=False,  # Tasks in private subnets
            service_name="rpa-ocr-service"
        )

        # Configure health check for the target group
        self.fargate_service.target_group.configure_health_check(
            path="/",
            port="5006",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3
        )

        # Configure ALB security group to allow HTTP traffic
        self.fargate_service.load_balancer.connections.allow_from_any_ipv4(
            ec2.Port.tcp(80),
            description="Allow inbound HTTP traffic"
        )

        # Configure service auto-scaling
        scaling = self.fargate_service.service.auto_scale_task_count(
            max_capacity=10,
            min_capacity=1
        )
        
        # Scale based on CPU utilization
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(300)
        )

        # Scale based on memory utilization
        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(300)
        )

        # CloudFormation Outputs
        CfnOutput(
            self, "LoadBalancerDNS",
            value=self.fargate_service.load_balancer.load_balancer_dns_name,
            description="DNS name of the Application Load Balancer"
        )

        CfnOutput(
            self, "ServiceName",
            value=self.fargate_service.service.service_name,
            description="Name of the ECS service"
        )

        CfnOutput(
            self, "ClusterName",
            value=cluster.cluster_name,
            description="Name of the ECS cluster"
        )

        CfnOutput(
            self, "VpcId",
            value=vpc.vpc_id,
            description="ID of the VPC"
        )

        CfnOutput(
            self, "TaskDefinitionArn",
            value=task_definition.task_definition_arn,
            description="ARN of the ECS task definition"
        )
