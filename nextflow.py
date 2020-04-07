# Imports
import argparse
from datetime import datetime
import json
import logging
import os
import re
import subprocess
from S3Manager import Batch, S3

# Define logger
import logging
logging.basicConfig(format="%(asctime)s — %(name)s — %(levelname)s — %(funcName)s:%(lineno)d — %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


def write_keys(config, fout, indent=0):
    for key in sorted(config):
        value = config[key]
        fout.write("\t" * indent)
        if type(value) == dict:
            fout.write(f"{key} {{\n")
            write_keys(value, fout, indent + 1)
        else:
            if type(value) == str:
                value = f"'{value}'"
            elif type(value) == bool:
                value = str(value).lower()
            fout.write(f"{key} = {str(value)}\n")
    fout.write("\t" * (indent - 1))
    if indent:
        fout.write("}\n")


def create_default_config(args):
    # Setup config arguments
    config = {
        "report": {
            "enabled": True
        },
        "timeline": {
            "enabled": True
        },
        "trace": {
            "enabled": True,
            "raw": True
        },
        "process": {
            "executor": "awsbatch",
            "cache": "lenient",
            "queue": args.queue,
            "errorStrategy": args.error_strategy,
            "maxRetries": int(args.max_retries),
            "publishDir": {
                "path": args.publish_dir,
                "mode": "symlink",
                "enabled": True
            }
        },
        "aws": {
            "batch": {
                "cliPath": "/miniconda/bin/aws",
                "volumes": ["/resource", "/nextflow"]
            },
            "region": args.region,
            "client": {
                "maxConnections": 20
            }
        },
        "executor": {
            "queueSize": 5000,
            "submitRateLimit": "1 sec"
        },
        "workDir": args.work_bucket
    }

    # Write config file
    # try:
    #     nextflow_config_path = f"{os.environ['AWS_BATCH_JOB_ID']}.{os.environ['AWS_BATCH_JOB_ATTEMPT']}.config"
    # except KeyError:
    #     nextflow_config_path = "nextflow.config"
    # with open(nextflow_config_path, "w") as fout:
    #     write_keys(config, fout)

    with open("nextflow.config", "w") as fout:
        write_keys(config, fout)

    with open("nextflow.json", "w") as fout:
        json.dump(config, fout)


def run_command(command):
    log.info(f"Running command: {' '.join(command)}")
    subprocess.run(command, check=True)


def run_nextflow(args):
    # Define executable
    executable = ["/usr/local/bin/nextflow"]

    # Specify the correct Nextflow version to use
    if args.nextflow_version != "latest":
        os.environ["NXF_VER"] = args.nextflow_version

    # Pull project
    log.info("Pulling project repository")
    run_command(
        executable + [
            "pull",
            args.project,
            "-revision",
            args.revision
        ]
    )

    # Define config arguments
    config_declarator = "-C" if args.explicit_configs else "-c"
    for config in args.configs:
        executable.extend([config_declarator, config])

    # Print config
    log.info("Printing configuration")
    run_command(
        executable + [
            "config",
            args.project
        ]
    )

    # Define project definition options
    executable.extend([
        "run",
        args.project,
        "-revision",
        args.revision
    ])

    # Define optional parameters
    if not args.no_cache:
        executable.extend(["-resume"])

    if args.generate_reports:
        executable.extend([
            "-with-trace",
            "-with-report",
            "-with-timeline",
            "-with-dag"
        ])

    # Run worklow
    log.info("Running workflow")
    run_command(executable)


def download_config(config_file):
    assert config_file.startswith("s3://")
    bucket, key = re.findall(r"s3://(.+?)/(.+)", config_file)[0]
    path = os.path.join(pipeline_dir, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    S3().download_file(path, bucket, key, overwrite=True)
    return path


def verify_batch_queue(args):
    # Check AWS Batch queue health
    response = Batch(region=args.region).client.describe_job_queues(jobQueues=[args.queue])['jobQueues']
    if not response:
        raise Exception(f"No queues available that match {args.queue}.")
    assert ((response[0]['state'] == "ENABLED") and (response[0]['status'] == "VALID"))


if __name__ == "__main__":
    # Init logger
    # logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    log.info("Entering Nextflow wrapper script")

    # Define arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow_id", required=True, help="Workflow ID.")
    parser.add_argument("--queue", default="arn:aws:batch:us-west-2:157538628385:job-queue/JobQueue-b41f70740f8eab7", help="AWS Batch queue ARN to use.")
    parser.add_argument("--error_strategy", action="store", default="retry", choices=["terminate", "finish", "ignore", "retry"], help="Define how an error condition is managed by the process.")
    parser.add_argument("--max_retries", action="store", default=0, help="Specify the maximum number of times a process can fail when using the retry error strategy.")
    parser.add_argument("--project", action="store", default="https://github.com/pjongeneel/nextflow_project.git", help="Github repo containing nextflow workflow.")
    parser.add_argument("--revision", action="store", default="master", help="Revision of the project to run (either a git branch, tag or commit SHA)")
    parser.add_argument("--publish_dir", action="store", help="Directory to copy outputs to. Automatically set if left blank.")
    parser.add_argument("--work_bucket", action="store", default="s3://patrick.poc", help="S3 bucket to use for work dir")
    parser.add_argument("--no_cache", action="store_true", help="Don't use cache to resume run, if possible.")
    parser.add_argument("--generate_reports", action="store_true", help="Generate nexflow standard reports, such as the trace, dag, timeline, report files.")
    parser.add_argument("--nextflow_version", action="store", default="latest", help="Nextflow version to use.")
    parser.add_argument("--configs", action="store", nargs="*", default=["s3://patrick.poc/nextflow/sample.config"], help="Ordered file(s) with nextflow parameters specific to this workflow.")
    parser.add_argument("--explicit_configs", action="store_true", help="Use only the provided nextflow configuration files, and do not import default config settings from the project or this docker image.")
    args = parser.parse_args()

    # Verify job queue status and set region
    args.region = re.findall(r"arn:aws:batch:(.+-.+-\d+)", args.queue)[0]
    verify_batch_queue(args)

    # Initialize pipeline variables and dirs
    pipeline_dir = os.path.join("/nextflow/workflows", str(args.workflow_id))
    nextflow_dir = os.path.join(pipeline_dir, "nextflow")
    os.makedirs(nextflow_dir, exist_ok=True)
    os.chdir(nextflow_dir)

    # Set work_bucket and publish dir
    args.work_bucket = os.path.join(args.work_bucket, pipeline_dir.lstrip("/"))
    if not args.publish_dir:
        args.publish_dir = pipeline_dir

    # Write default nextflow configuration file
    create_default_config(args)

    # Download any additional configuration files (parameters, etc)
    if args.configs:
        args.configs = map(download_config, args.configs)

    # Run nextflow executable given the project and project parameters
    run_nextflow(args)
