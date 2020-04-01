# Imports
import argparse
import logging
import os
import re
import subprocess
from S3Manager import S3

# Define logger
import logging
logging.basicConfig(format="%(asctime)s — %(name)s — %(levelname)s — %(funcName)s:%(lineno)d — %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


def download_configs(args, root_dir):
    # Create S3 manager object for downloading configuration files
    s3_manager = S3(region=args.region)

    # Download each config file to root dir
    paths = []
    for conf in args.configs:
        assert conf.startswith("s3://")  # Must be an S3 path for now
        bucket, key = re.findall(r"s3://(.+?)/(.+)", conf)[0]
        path = os.path.join(root_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
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


def create_default_config(args, root_dir):
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

    with open(os.path.join(root_dir, "nextflow.config"), "w") as fout:
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

    # Print config
    print_command = command + ["config"]
    log.info("Printing configuration...")
    log.info(f"Running command: {' '.join(print_command)}")
    subprocess.run(print_command, check=True)

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
    log.info(f"Running command: {' '.join(command)}")
    subprocess.run(command, check=True)


if __name__ == "__main__":
    # Init logger
    # logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    log.info("Entering Nextflow wrapper script")

    # Define arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="arn:aws:batch:us-west-2:157538628385:job-queue/JobQueue-b41f70740f8eab7", help="AWS Batch queue arn to use.")
    parser.add_argument("--error_strategy", action="store", default="retry", choices=["terminate", "finish", "ignore", "retry"], help="Define how an error condition is managed by the process.")
    parser.add_argument("--max_errors", action="store", default=1, help="Specify the maximum number of times a process can fail when using the retry error strategy.")
    parser.add_argument("--project", action="store", default="https://github.com/pjongeneel/nextflow_project.git", help="Github repo containing nextflow workflow.")
    parser.add_argument("--revision", action="store", default="master", help="Revision of the project to run (either a git branch, tag or commit SHA)")
    parser.add_argument("--publish_dir", action="store", default="/nextflow/outputs", help="Directory to copy outputs to.")
    parser.add_argument("--work_bucket", action="store", default="s3://patrick.poc/nextflow_work", help="S3 bucket to use for work dir")
    parser.add_argument("--region", action="store", default="us-west-2", help="AWS region to deploy to.")
    parser.add_argument("--no_cache", action="store_true", help="Don't use cache to resume run.")
    parser.add_argument("--nextflow_version", action="store", default="latest", help="Nextflow version to use.")
    parser.add_argument("--configs", action="store", nargs="*", default=["s3://patrick.poc/nextflow/sample.config"], help="File(s) with nextflow parameters specific to this workflow")
    parser.add_argument("--explicit_configs", action="store_true", help="Use only the provided nextflow configuration files, and do not import default config settings from the project or this docker image.")
    args = parser.parse_args()

    # Define and create nextflow run directory
    try:
        root_dir = os.path.join("/nextflow/jobs", os.environ["AWS_BATCH_JOB_ID"], os.environ["AWS_BATCH_JOB_ATTEMPT"])
        os.makedirs(root_dir, exist_ok=False)
    except KeyError:
        root_dir = os.path.join("/nextflow/jobs/test")
        os.makedirs(root_dir, exist_ok=True)
    os.chdir(root_dir)

    # Download any additional configuration files (parameters, etc)
    if args.configs:
        args.configs = download_configs(args, root_dir)

    # Write default nextflow configuration file
    create_default_config(args, root_dir)

    # Run nextflow executable given the project and project parameters
    run_nextflow(args)
