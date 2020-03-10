# Define logger
import logging
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


# Imports
import argparse
import json
import logging
import os
import re
import subprocess
from S3Manager import S3Manager


def download_configs(args):
    # Create S3 manager object for downloading configuration files
    s3_manager = S3Manager()

    # Define root dir to put config files in
    os.environ["AWS_BATCH_JOB_ID"] = "1"
    os.environ["AWS_BATCH_JOB_ATTEMPT"] = "2"
    root = os.path.join("/nextflow/master", os.environ["AWS_BATCH_JOB_ID"], os.environ["AWS_BATCH_JOB_ATTEMPT"])

    # Download each config file to root dir
    paths = []
    for conf in args.configs:
        assert conf.startswith("s3://")  # Must be an S3 path for now
        bucket, key = re.findall(r"s3://(.+?)/(.+)", conf)[0]
        path = os.path.join(root, key)
        s3_manager.download_file(path, bucket, key, overwrite=True)
        paths.append(path)
    return paths


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
        "weblog": {
            "enabled": True
        },
        "process": {
            "executor": "awsbatch",
            "cache": "lenient",
            "queue": args.queue,
            "errorStrategy": args.error_strategy,
            "maxErrors": int(args.max_errors),
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
            "region": args.region
        },
        "executor": {
            "queueSize": 5000,
            "submitRateLimit": "1 sec"
        },
        "workDir": os.path.join("/nextflow", "work")
    }

    with open("nextflow.config", "w") as fout:
        write_keys(config, fout)


def run_nextflow(args):
    # Define executable
    command = ["/usr/local/bin/nextflow"]

    # Specify the correct Nextflow version to use
    if args.nextflow_version != "latest":
        os.environ["NXF_VER"] = args.nextflow_version

    # Define sample / workflow specific parameters
    config_declarator = "-C" if args.explicit_configs else "-c"
    for config in args.configs:
        command.extend([config_declarator, config])

    # Define project definition options
    command.extend([
        "run",
        args.project,
        "-revision",
        args.revision,
        "-latest"
    ])

    # Define optional parameters
    if not args.no_cache:
        command.extend(["-resume"])
    command.extend([
            "-with-trace",
            "-with-report",
            "-with-timeline",
            "-with-weblog",
            "-with-dag"
    ])

    # Run command
    log.info("Command: {0}".format(" ".join(command)))
    subprocess.run(command, check=True)
    # try:
    # subprocess.run(command, check=True)
    # except subprocess.CalledProcessError as e:
    #     logging.error("OH NO")
    #     raise e


if __name__ == "__main__":
    # Init logger
    # logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    log.info("Entering Nextflow wrapper script")

    # Define arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="arn:aws:batch:us-west-1:935013742570:job-queue/JobQueue-8992da5e37f02fb", help="AWS Batch queue arn to use.")
    parser.add_argument("--error_strategy", action="store", default="retry", choices=["terminate", "finish", "ignore", "retry"], help="Define how an error condition is managed by the process.")
    parser.add_argument("--max_errors", action="store", default=1, help="Specify the maximum number of times a process can fail when using the retry error strategy.")
    parser.add_argument("--project", action="store", default="https://github.com/pjongeneel/nextflow_project.git", help="Github repo containing nextflow workflow.")
    parser.add_argument("--revision", action="store", default="master", help="Revision of the project to run (either a git branch, tag or commit SHA)")
    parser.add_argument("--publish_dir", action="store", default="/nextflow/outputs", help="Directory to copy outputs to.")
    parser.add_argument("--region", action="store", default="us-west-1", help="AWS region to deploy to.")
    parser.add_argument("--no_cache", action="store_true", help="Don't use cache to resume run.")
    parser.add_argument("--nextflow_version", action="store", default="latest", help="Nextflow version to use.")
    parser.add_argument("--configs", action="store", nargs="*", default=["s3://pipeline.poc/nextflow/sample.config"], help="File(s) with nextflow parameters specific to this workflow")
    parser.add_argument("--explicit_configs", action="store_true", help="Use only the provided nextflow configuration files, and do not import default config settings from the project or this docker image.")
    args = parser.parse_args()

    # Write default nextflow configuration file
    create_default_config(args)

    # Download any additional configuration files (parameters, etc)
    if args.configs:
        args.configs = download_configs(args)

    # Run nextflow executable given the project and project parameters
    run_nextflow(args)
