# Imports
import argparse
from aws import Batch, S3
from git import Repo
import logging
import os
import re
import shutil
import subprocess

# Define logger
import logging
logging.basicConfig(format="%(asctime)s — %(name)s — %(levelname)s — %(funcName)s:%(lineno)d — %(message)s", level=logging.DEBUG)
log = logging.getLogger(__name__)


def _write_nextflow_config(config, fout, indent=0):
    """Write nextflow config file, given dictionary of config arguments

    Args:
        config (dict): Nextflow configuration options
        fout (file object): File object to write to. Will be called as fout.write
        indent (int, optional): Indent for formatting. Not for external use. Defaults to 0.
    """

    for key in sorted(config):
        value = config[key]
        fout.write("\t" * indent)
        if type(value) == dict:
            fout.write(f"{key} {{\n")
            _write_nextflow_config(value, fout, indent + 1)
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
    """Creats the default nextflow.config file in the running directory of the nextflow workflow.

    Args:
        args (argparse.Namespace): Parsed arugments used for method.
    """

    # Setup config arguments
    config = {
        "report": {
            "enabled": args.generate_reports
        },
        "timeline": {
            "enabled": args.generate_reports
        },
        "trace": {
            "enabled": args.generate_reports,
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
                "volumes": ["/resources", "/nextflow"]
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
    with open("nextflow.config", "w") as fout:
        _write_nextflow_config(config, fout)


def download_repo(args):
    """Downloads the project repo provided to the script into the project dir for nextflow.

    Args:
        args (argparse.Namespace): Parsed arugments used for method.
    """

    # Remote old repos
    if os.path.isdir("project"):
        log.debug(f"Existing project found. Removing old project.")
        shutil.rmtree("project")

    # Check project name
    if not args.project.startswith("https://") or not args.project.endswith(".git"):
        raise Exception("Project must be a git repo which is of the form https://{host}/{repo_name}.git")

    # Clone project
    log.info(f"Cloning {args.project}")
    if "github" in args.project:
        repo = Repo.clone_from(
            url=args.project.replace("https://", f"https://{args.token}:x-oauth-basic@"),
            to_path="project",
            multi_options=['--recurse-submodules']
        )
    elif "stash" in args.project:
        os.environ['GIT_SSL_NO_VERIFY'] = 'true'
        repo = Repo.clone_from(
            url=args.project.replace("https://", f"https://x-token-auth:project@"),
            to_path="project",
            multi_options=['--recurse-submodules'],
            c=f"http.extraHeader=Authorization: Bearer {args.token}"
        )
    else:
        raise Exception(f"Source URL {args.project} not currently supported!")

    # Checkout correct revision
    repo.git.checkout(args.revision)


def run_command(command):
    """Runs a given subprocess command.

    Args:
        command (list): Command to be run.
    """

    log.info(f"Running command: {' '.join(command)}")
    subprocess.run(command, check=True)


def run_nextflow(args):
    """Runs the nextflow executable on the project.

    Args:
        args (argparse.Namespace): Parsed arugments used for method.
    """

    # Define executable
    executable = ["/usr/local/bin/nextflow"]

    # Specify the correct Nextflow version to use
    if args.nextflow_version != "latest":
        os.environ["NXF_VER"] = args.nextflow_version

    # Define config arguments
    config_declarator = "-C" if args.explicit_configs else "-c"
    for config in args.configs:
        executable.extend([config_declarator, config])

    # Print project config
    log.info("Printing configuration")
    run_command(
        executable + [
            "config",
            "project"
        ]
    )

    # Define run command
    executable.extend([
        "run",
        "project"
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


def download_file(s3_key, base_dir=None):
    """Downloads a file from S3

    Args:
        s3_key (str): S3 location of a file
        base_dir (str, optional): Directory to download files to. Defaults to current working dir.

    Returns:
        str: Path to downloaded file
    """

    assert s3_key.startswith("s3://")
    base_dir = base_dir if base_dir else os.getcwd()
    bucket, key = re.findall(r"s3://(.+?)/(.+)", s3_key)[0]
    S3().download_file(
        os.path.join(base_dir, key),
        bucket,
        key,
        overwrite=True
    )
    return os.path.join(base_dir, key)


def verify_batch_queue(args):
    """Checks that state == ENABLED and status == VALID for a batch queue.

    Args:
        args (argparse.Namespace): Parsed arugments used for method.

    Raises:
        Exception: Batch queue does not exist.
        Assertion Error: Batch queue is not healthy.
    """

    # Check AWS Batch queue health
    response = Batch(region_name=args.region).client.describe_job_queues(jobQueues=[args.queue])['jobQueues']
    if not response:
        raise Exception(f"No queues available that match {args.queue}.")
    assert ((response[0]['state'] == "ENABLED") and (response[0]['status'] == "VALID"))


def init_pipeline_directories(args):
    """Create pipeline directory structure on EFS.

    Args:
        args (argparse.Namespace): Parsed arugments used for method.
    """

    # Initialize pipeline dirs
    log.info("Initializing pipeline directories")
    pipeline_dir = os.path.join("/nextflow/workflows", str(args.workflow_id))
    nextflow_dir = os.path.join(pipeline_dir, "nextflow")
    os.makedirs(nextflow_dir, exist_ok=True)
    os.chdir(nextflow_dir)

    # Set work_bucket and publish dir
    args.work_bucket = os.path.join(args.work_bucket, pipeline_dir.lstrip("/"))
    if not args.publish_dir:
        args.publish_dir = pipeline_dir  # potentially change this with OS.environ variables AWS_BATCH_JOB_ID and AWS_BATCH_JOB_ATTEMPT


if __name__ == "__main__":
    log.info("Entering Nextflow wrapper script")

    # Define arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow_id", required=True, help="Workflow ID.")
    parser.add_argument("--queue", default="arn:aws:batch:us-west-2:157538628385:job-queue/JobQueue-309cc249183fcf1", help="AWS Batch queue ARN to use.")
    parser.add_argument("--error_strategy", action="store", default="retry", choices=["terminate", "finish", "ignore", "retry"], help="Define how an error condition is managed by the process.")
    parser.add_argument("--max_retries", action="store", default=0, help="Specify the maximum number of times a process can fail when using the retry error strategy.")
    parser.add_argument("--project", action="store", default="https://github.com/pjongeneel/nextflow_project.git", help="Github repo containing nextflow workflow.")
    parser.add_argument("--token", action="store", default="", help="Git access token.")
    parser.add_argument("--revision", action="store", default="master", help="Revision of the project to run (either a git branch, tag or commit SHA)")
    parser.add_argument("--publish_dir", action="store", help="Directory to copy outputs to. Automatically set if left blank.")
    parser.add_argument("--work_bucket", action="store", default="s3://patrick.poc", help="S3 bucket to use for work dir")
    parser.add_argument("--no_cache", action="store_true", help="Don't use cache to resume run, if possible.")
    parser.add_argument("--generate_reports", action="store_true", help="Generate nexflow standard reports, such as the trace, dag, timeline, report files.")
    parser.add_argument("--nextflow_version", action="store", default="latest", help="Nextflow version to use.")
    parser.add_argument("--configs", action="store", nargs="*", default=["s3://patrick.poc/nextflow/sample.config"], help="Ordered file(s) with nextflow parameters specific to this workflow.")
    parser.add_argument("--explicit_configs", action="store_true", help="Use only the provided nextflow configuration files, and do not import default config settings from the project or this docker image.")
    args = parser.parse_args()

    # Initialize pipeline
    init_pipeline_directories(args)

    # Set region automatically from job queue
    args.region = re.findall(r"arn:aws:batch:(.+?-.+?-\d+)", args.queue)[0]

    # Verify job queue status
    verify_batch_queue(args)

    # Write default nextflow configuration file
    create_default_config(args)

    # Download any additional configuration files (parameters, etc)
    if args.configs:
        log.info("Downloading additional configuration files")
        args.configs = map(download_file, args.configs)

    # Pull project
    download_repo(args)

    # Run nextflow executable given the project and project parameters
    run_nextflow(args)
