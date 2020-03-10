# Define logger
import logging
log = logging.getLogger(__name__)

# Imports
import boto3
import os
import time
from botocore.errorfactory import ClientError


class S3Manager:

    def __init__(self):
        self.client = boto3.client("s3")

    def exists_on_s3(self, bucket, key, empty_ok=True):
        try:
            results = self.client.head_object(Bucket=bucket, Key=key)
            if empty_ok or int(results["ContentLength"]) > 0:
                return True
            else:
                return False
        except ClientError:
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
        assert key.endswith("/") and not key.startswith("/")
        s3_keys = []
        paginator = self.client.get_paginator("list_objects")
        for result in paginator.paginate(Bucket=bucket, Prefix=key, Delimiter="/"):
            if result["CommonPrefixes"]:
                for subdir in result["CommonPrefixes"]:
                    s3_keys.extend(self.walk_s3_dir(bucket, subdir["Prefix"]))
            if result["Contents"]:
                s3_keys.extend([k for k in result["Contents"] if not k.endswith("/")])
        return s3_keys
