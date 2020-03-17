# Imports
import boto3
import botocore
import json
import os
import time

# Define logger
import logging
log = logging.getLogger(__name__)


# Some utility functions
def print_response(response):
    log.info("AWS response:")
    log.info(json.dumps(response, indent=2, default=str))


class VPC:

    def __init__(self, profile=None, region=None):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.resource = self.session.resource("ec2")

    def get_vpc(self, vpc_id):
        try:
            vpc = self.resource.Vpc(vpc_id)
            vpc.load()
        except botocore.exceptions.ClientError as e:
            log.error(f"VPC Id {vpc_id} not valid\n")
            raise e
        return vpc

    def get_subnet_ids(self, vpc_id):
        return [i.id for i in self.get_vpc(vpc_id).subnets.all()]

    def check_subnet_ids(self, subnet_ids, vpc_id):
        available_subnet_ids = self.get_subnet_ids(vpc_id)
        try:
            assert all([subnet_id in available_subnet_ids for subnet_id in subnet_ids])
        except AssertionError as e:
            log.error(f"Subnet Ids provided ({subnet_ids}) not in available subnets for the VPC ({vpc_id}:{available_subnet_ids})")
            raise e
        return subnet_ids


class Cloudformation:

    def __init__(self, profile=None, region=None):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.client = self.session.client("cloudformation")

    def create_stack(self, stack_name, template, parameters=[], capabilities="CAPABILITY_NAMED_IAM", on_failure="ROLLBACK"):
        response = self.client.create_stack(
            StackName=stack_name,
            Parameters=parameters,
            TemplateBody=template.to_json(),
            Capabilities=[
                capabilities,
            ],
            OnFailure=on_failure
        )
        print_response(response)
        return response

    def delete_stack(self, *args, stack_name):
        response = self.client.delete_stack(StackName=stack_name)
        print_response(response)
        return response

    def describe_stack(self, *args, stack_name):
        response = self.client.describe_stacks()
        stacks = [stack for stack in response['Stacks'] if stack_name == stack["StackName"]]
        response["Stacks"] = stacks
        print_response(response)
        return response


class S3:

    def __init__(self, profile=None, region=None):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.client = self.session.client("s3")

    def exists_on_s3(self, bucket, key, empty_ok=True):
        try:
            results = self.client.head_object(Bucket=bucket, Key=key)
            return (empty_ok or int(results["ContentLength"]) > 0)
        except botocore.errorfactory.ClientError:
            return False

    def upload_file(self, path, bucket, key, overwrite=True):
        log.info(f"Uploading {path} to s3://{bucket}/{key}")
        if overwrite or not self.exists_on_s3(bucket, key):
            start = time.time()
            self.client.upload_file(path, bucket, key)
            log.debug(f"Upload complete in {int(time.time() - start)} seconds")
        log.debug(f"Upload skipped")

    def download_file(self, path, bucket, key, overwrite=True):
        log.info(f"Downloading s3://{bucket}/{key} to {path}")
        if overwrite or not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            start = time.time()
            self.client.download_file(bucket, key, path)
            log.debug(f"Download complete in {int(time.time() - start)} seconds")
        log.debug(f"Download skipped")

    def walk_s3_dir(self, bucket, key):
        assert (key.endswith("/") and not key.startswith("/"))
        s3_keys = []
        paginator = self.client.get_paginator("list_objects")
        for result in paginator.paginate(Bucket=bucket, Prefix=key, Delimiter="/"):
            if result["CommonPrefixes"]:
                for subdir in result["CommonPrefixes"]:
                    s3_keys.extend(self.walk_s3_dir(bucket, subdir["Prefix"]))
            if result["Contents"]:
                s3_keys.extend([k for k in result["Contents"] if not k.endswith("/")])
        return s3_keys
