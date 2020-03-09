import argparse
import json
import logging
import os
import subprocess


def write_keys(config, fout, indent=0):
    for key in sorted(config):
        value = config[key]
        fout.write("\t" * indent)
        if type(value) == dict:
            fout.write(f"{key} = {{\n")
            write_keys(value, fout, indent + 1)
        else:
            if type(value) == str:
                value = f"'{value}'"
            elif type(value) == bool:
                value = str(value).lower()
            fout.write(f"{key}={str(value)}\n")
    fout.write("\t" * (indent - 1))
    fout.write("}\n")


def create_default_config(args):
    os.environ["AWS_BATCH_JOB_ID"] = "g"
    os.environ["AWS_BATCH_JOB_ATTEMPT"] = "a"
    config = {
        "manifest": {
            "nextflowVersion": "19.10.0"
        },
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
            "errorStrategy": args.errorStrategy,
            "maxErrors": int(args.maxErrors),
            "publishDir": args.publishDir
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
        "workDir": os.path.join("/nextflow", "runs", os.environ["AWS_BATCH_JOB_ID"], os.environ["AWS_BATCH_JOB_ATTEMPT"])
    }

    with open("nextflow.config", "w") as fout:
        write_keys(config, fout)


def run_nextflow(project, params):
    command = ["/usr/local/bin/nextflow", "run", project, "-c", params]
    logging.info("Command: {0}".format(" ".join(command)))
    # try:
    #     subprocess.run(command, check=True)
    # except subprocess.CalledProcessError as e:
    #     logging.error("OH NO")
    #     raise e


if __name__ == "__main__":
    # Init logger
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.DEBUG)
    logging.info("Entering Nextflow wrapper script")

    # Define arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="arn:aws:batch:us-west-1:935013742570:job-queue/JobQueue-8992da5e37f02fb", help="AWS Batch queue arn to use.")
    parser.add_argument("--errorStrategy", action="store", default="retry", choices=["terminate", "finish", "ignore", "retry"], help="Define how an error condition is managed by the process.")
    parser.add_argument("--maxErrors", action="store", default=1, help="Specify the maximum number of times a process can fail when using the retry error strategy.")
    parser.add_argument("--project", action="store", default="https://github.com/pjongeneel/nextflow_project.git", help="Github repo containing nextflow workflow.")
    parser.add_argument("--publishDir", action="store", default="/nextflow/outputs", help="Directory to copy outputs to.")
    parser.add_argument("--region", action="store", default="us-west-1", help="AWS region to deploy to.")
    parser.add_argument("--run_config", action="store", default="run.config", help="File with nextflow parameters specific to this workflow")
    args = parser.parse_args()

    # Write default nextflow configuration file
    create_default_config(args)

    # Run nextflow executable given the project and project parameters
    run_nextflow(args.project, args.run_config)
